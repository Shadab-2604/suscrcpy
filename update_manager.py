"""Automatic GitHub update system for SUSCRCPY.

Handles:
- GitHub Releases API querying (HTTPS only)
- Semantic version comparison
- Release asset resolution (suscrcpy-source.zip and SHA256SUMS)
- SHA-256 integrity verification
- Safe zip extraction with path-traversal (Zip Slip) protection
- Atomic staging, backup, and rollback mechanisms
- Privilege and path checks for system-wide /opt/suscrcpy updates
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from version import (
    API_LATEST_RELEASE_URL,
    APP_NAME,
    APP_VERSION,
    GITHUB_URL,
    is_newer_version,
    parse_semver,
)

logger = logging.getLogger("suscrcpy.update_manager")

USER_AGENT = f"{APP_NAME}-Updater/{APP_VERSION} (Linux; +{GITHUB_URL})"
MAX_DOWNLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB safety limit
DEFAULT_TIMEOUT_SECS = 25
DEFAULT_INSTALL_DIR = Path("/opt/suscrcpy")


class UpdateError(RuntimeError):
    """Base exception for update failures."""
    pass


class NoReleasesPublishedError(UpdateError):
    """Raised when repository exists but no release tags are published yet."""
    pass


class ChecksumMismatchError(UpdateError):
    """Raised when SHA-256 hash does not match SHA256SUMS."""
    pass


class ArchiveSecurityError(UpdateError):
    """Raised when zip archive contains illegal paths (Zip Slip vulnerability)."""
    pass


class PermissionRequiredError(UpdateError):
    """Raised when update requires elevated permissions."""
    pass


@dataclasses.dataclass
class ReleaseAsset:
    """GitHub Release asset information."""
    name: str
    download_url: str
    size: int


@dataclasses.dataclass
class ReleaseInfo:
    """Structured information about a GitHub release."""
    tag_name: str
    version: str
    name: str
    body: str
    published_at: str
    html_url: str
    assets: Dict[str, ReleaseAsset]
    is_update_available: bool

    @property
    def source_archive_asset(self) -> Optional[ReleaseAsset]:
        """Find the official source zip archive asset."""
        for name in ("suscrcpy-source.zip", f"suscrcpy-{self.version}.zip", "suscrcpy.zip"):
            if name in self.assets:
                return self.assets[name]
        return None

    @property
    def checksums_asset(self) -> Optional[ReleaseAsset]:
        """Find the SHA256SUMS asset."""
        for name in ("SHA256SUMS", "sha256sums.txt", "SHA256SUMS.txt"):
            if name in self.assets:
                return self.assets[name]
        return None


class UpdateManager:
    """Manages release discovery, download, verification, and atomic installation."""

    def __init__(
        self,
        current_version: str = APP_VERSION,
        install_dir: Optional[Path] = None,
        api_url: str = API_LATEST_RELEASE_URL,
    ) -> None:
        self.current_version = current_version
        self.install_dir = Path(install_dir) if install_dir else DEFAULT_INSTALL_DIR
        self.api_url = api_url

    def fetch_latest_release(self, timeout: int = DEFAULT_TIMEOUT_SECS) -> ReleaseInfo:
        """Fetch and parse latest release information from GitHub Releases API."""
        if not self.api_url.startswith("https://"):
            raise UpdateError("Security violation: Updates must use HTTPS endpoints.")

        req = urllib.request.Request(
            self.api_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/vnd.github.v3+json",
            },
        )

        ctx = ssl.create_default_context()

        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                if response.status != 200:
                    raise UpdateError(f"GitHub API returned HTTP {response.status}")
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NoReleasesPublishedError(
                    f"No stable releases have been published yet on GitHub repository ({GITHUB_URL})."
                ) from e
            if e.code in (403, 429):
                raise UpdateError(
                    "GitHub API rate limit exceeded. Please wait a few minutes and try again."
                ) from e
            raise UpdateError(f"HTTP error checking GitHub release: {e}") from e
        except urllib.error.URLError as e:
            raise UpdateError(
                f"Failed to connect to GitHub ({e.reason}). Please check your internet connection."
            ) from e
        except json.JSONDecodeError as e:
            raise UpdateError(f"Invalid JSON response from GitHub API: {e}") from e

        return self._parse_release_json(data)

    def _parse_release_json(self, data: dict) -> ReleaseInfo:
        """Parse raw release JSON into ReleaseInfo dataclass."""
        tag = data.get("tag_name", "").strip()
        version = tag.lstrip("vV")
        name = data.get("name") or tag
        body = data.get("body") or "No release notes provided."
        published_at = data.get("published_at", "")
        html_url = data.get("html_url") or GITHUB_URL

        assets: Dict[str, ReleaseAsset] = {}
        for asset in data.get("assets", []):
            aname = asset.get("name", "")
            url = asset.get("browser_download_url", "")
            size = asset.get("size", 0)
            if aname and url:
                assets[aname] = ReleaseAsset(name=aname, download_url=url, size=size)

        is_avail = is_newer_version(version, self.current_version)

        return ReleaseInfo(
            tag_name=tag,
            version=version,
            name=name,
            body=body,
            published_at=published_at,
            html_url=html_url,
            assets=assets,
            is_update_available=is_avail,
        )

    def download_file(
        self,
        url: str,
        dest_path: Path,
        max_size: int = MAX_DOWNLOAD_SIZE_BYTES,
        timeout: int = DEFAULT_TIMEOUT_SECS,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download file securely via HTTPS with size checking."""
        if not url.startswith("https://"):
            raise UpdateError("Insecure download URL rejected: HTTPS is strictly required.")

        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        ctx = ssl.create_default_context()

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        total_downloaded = 0

        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                content_length = response.headers.get("Content-Length")
                total_size = int(content_length) if content_length and content_length.isdigit() else 0

                if total_size > max_size:
                    raise UpdateError(
                        f"Asset size ({total_size} bytes) exceeds maximum limit ({max_size} bytes)."
                    )

                with open(dest_path, "wb") as f:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        total_downloaded += len(chunk)
                        if total_downloaded > max_size:
                            raise UpdateError("Download exceeded maximum safe file size limit.")
                        f.write(chunk)
                        if progress_callback:
                            progress_callback(total_downloaded, total_size)
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink()
            if isinstance(e, UpdateError):
                raise
            raise UpdateError(f"Failed to download asset from {url}: {e}") from e

        return dest_path

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calculate the SHA-256 digest of a local file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest().lower()

    @staticmethod
    def parse_checksums_file(content: str) -> Dict[str, str]:
        """Parse standard sha256sum output format (<hash>  <filename>)."""
        checksums: Dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                file_hash, file_name = parts[0].strip().lower(), parts[1].strip().lstrip("*")
                checksums[file_name] = file_hash
        return checksums

    @staticmethod
    def validate_zip_members(zip_ref: zipfile.ZipFile, target_dir: Path) -> None:
        """Inspect all archive paths to prevent directory traversal attacks (Zip Slip)."""
        target_dir_resolved = target_dir.resolve()
        for member in zip_ref.infolist():
            filename = member.filename
            if os.path.isabs(filename):
                raise ArchiveSecurityError(f"Illegal absolute path in archive: {filename}")

            dest = (target_dir / filename).resolve()
            if target_dir_resolved not in dest.parents and dest != target_dir_resolved:
                raise ArchiveSecurityError(
                    f"Directory traversal attempt detected in archive member: {filename}"
                )

    def perform_update(
        self,
        release: Optional[ReleaseInfo] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> str:
        """Execute the full, atomic update lifecycle with backup and rollback."""
        if progress_callback:
            progress_callback("Checking for updates...", 0.05)

        if not release:
            release = self.fetch_latest_release()

        if not release.is_update_available:
            return f"Already up-to-date ({self.current_version})."

        # Check permissions on install directory
        target_dir = self.install_dir
        if target_dir.exists() and not os.access(target_dir, os.W_OK):
            raise PermissionRequiredError(
                f"Cannot write to installation directory '{target_dir}'.\n"
                "Please run the update command with administrator privileges:\n"
                "    sudo suscrcpy --update"
            )

        archive_asset = release.source_archive_asset
        if not archive_asset:
            raise UpdateError(
                f"Release {release.tag_name} is missing the required source archive "
                "(suscrcpy-source.zip)."
            )

        checksum_asset = release.checksums_asset
        if not checksum_asset:
            raise UpdateError(
                f"Release {release.tag_name} is missing the cryptographic checksums file (SHA256SUMS)."
            )

        # Use secure temporary directory under system tmp
        temp_dir_base = tempfile.mkdtemp(prefix="suscrcpy_update_")
        temp_dir = Path(temp_dir_base)
        backup_dir = None

        try:
            # 1. Download SHA256SUMS
            if progress_callback:
                progress_callback("Downloading checksums...", 0.15)
            checksums_file = temp_dir / "SHA256SUMS"
            self.download_file(checksum_asset.download_url, checksums_file)
            checksums = self.parse_checksums_file(checksums_file.read_text(encoding="utf-8"))

            expected_hash = checksums.get(archive_asset.name)
            if not expected_hash:
                raise ChecksumMismatchError(
                    f"No checksum entry for '{archive_asset.name}' found in release SHA256SUMS."
                )

            # 2. Download source archive
            if progress_callback:
                progress_callback("Downloading release archive...", 0.35)
            archive_file = temp_dir / archive_asset.name

            def on_download_progress(downloaded: int, total: int) -> None:
                if total > 0 and progress_callback:
                    pct = 0.35 + (downloaded / total) * 0.35
                    progress_callback(
                        f"Downloading ({downloaded // 1024} KB / {total // 1024} KB)...", pct
                    )

            self.download_file(
                archive_asset.download_url, archive_file, progress_callback=on_download_progress
            )

            # 3. Cryptographic SHA-256 verification
            if progress_callback:
                progress_callback("Verifying archive integrity...", 0.75)
            actual_hash = self.calculate_sha256(archive_file)
            if actual_hash != expected_hash:
                raise ChecksumMismatchError(
                    f"SHA-256 integrity check failed!\n"
                    f"Expected: {expected_hash}\n"
                    f"Actual:   {actual_hash}\n"
                    "The download may be corrupted or tampered with. Update aborted."
                )

            # 4. Safe archive extraction to staging directory
            if progress_callback:
                progress_callback("Validating archive structure...", 0.80)
            staging_dir = temp_dir / "staged"
            staging_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(archive_file, "r") as z:
                self.validate_zip_members(z, staging_dir)
                z.extractall(staging_dir)

            # Locate root of extracted files (handles archive with or without top-level dir)
            extracted_items = list(staging_dir.iterdir())
            if len(extracted_items) == 1 and extracted_items[0].is_dir() and (extracted_items[0] / "main.py").exists():
                source_root = extracted_items[0]
            else:
                source_root = staging_dir

            if not (source_root / "main.py").exists():
                raise UpdateError("Extracted archive does not contain 'main.py' entrypoint.")

            # 5. Create backup of current installation
            if target_dir.exists():
                if progress_callback:
                    progress_callback("Backing up current installation...", 0.85)
                backup_dir = Path(tempfile.mkdtemp(prefix="suscrcpy_backup_"))
                shutil.copytree(target_dir, backup_dir / "current", dirs_exist_ok=True)

            # 6. Atomic replacement of application files
            if progress_callback:
                progress_callback("Installing updated version...", 0.90)
            target_dir.mkdir(parents=True, exist_ok=True)

            # Copy essential directories and files
            copy_targets = [
                "core",
                "ui",
                "platform",
                "resources",
                "main.py",
                "version.py",
                "update_manager.py",
                "requirements.txt",
                "uninstall.sh",
                "LICENSE",
            ]

            for item in copy_targets:
                src_item = source_root / item
                dst_item = target_dir / item
                if src_item.exists():
                    if src_item.is_dir():
                        shutil.rmtree(dst_item, ignore_errors=True)
                        shutil.copytree(src_item, dst_item)
                    else:
                        shutil.copy2(src_item, dst_item)

            # Ensure proper execution permissions
            for script_name in ("main.py", "uninstall.sh"):
                p = target_dir / script_name
                if p.exists():
                    os.chmod(p, 0o755)

            # 7. Verification dry-run of newly installed files
            if progress_callback:
                progress_callback("Verifying installation...", 0.95)
            verify_res = subprocess.run(
                [sys.executable, str(target_dir / "main.py"), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if verify_res.returncode != 0:
                raise UpdateError(
                    f"Updated application failed self-test verification: {verify_res.stderr.strip()}"
                )

            if progress_callback:
                progress_callback("Update completed successfully!", 1.0)

            return f"Successfully updated SUSCRCPY to version {release.version}."

        except Exception as e:
            logger.error("Update failed: %s. Initiating rollback...", e)
            # Automatic Rollback
            if backup_dir and (backup_dir / "current").exists() and target_dir.exists():
                logger.info("Restoring backup from %s...", backup_dir)
                try:
                    shutil.copytree(backup_dir / "current", target_dir, dirs_exist_ok=True)
                    logger.info("Rollback succeeded.")
                except Exception as rb_err:
                    logger.critical("Rollback failed: %s", rb_err)
            raise

        finally:
            # Clean up temporary staging files
            shutil.rmtree(temp_dir, ignore_errors=True)
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
