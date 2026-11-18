"""Unit tests for GitHub release discovery, update parsing, and rollback mechanics."""
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from update_manager import (
    ChecksumMismatchError,
    ReleaseAsset,
    ReleaseInfo,
    UpdateError,
    UpdateManager,
)


class TestUpdateManager(unittest.TestCase):
    """Test suite for UpdateManager lifecycle, error handling, and rollback."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.install_dir = self.temp_path / "opt_suscrcpy"
        self.install_dir.mkdir()

        # Seed mock installation
        (self.install_dir / "main.py").write_text("print('version 1.0.0')")
        (self.install_dir / "version.py").write_text("APP_VERSION = '1.0.0'")

        self.manager = UpdateManager(current_version="1.0.0", install_dir=self.install_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parse_release_json_newer_available(self) -> None:
        mock_data = {
            "tag_name": "v2.1.0",
            "name": "SUSCRCPY 2.1.0 Release",
            "body": "Changelog:\n- New features",
            "published_at": "2026-11-18T10:00:00Z",
            "html_url": "https://github.com/Shadab-2604/suscrcpy/releases/tag/v2.1.0",
            "assets": [
                {
                    "name": "suscrcpy-source.zip",
                    "browser_download_url": "https://github.com/Shadab-2604/suscrcpy/releases/download/v2.1.0/suscrcpy-source.zip",
                    "size": 1048576,
                },
                {
                    "name": "SHA256SUMS",
                    "browser_download_url": "https://github.com/Shadab-2604/suscrcpy/releases/download/v2.1.0/SHA256SUMS",
                    "size": 256,
                },
            ],
        }

        info = self.manager._parse_release_json(mock_data)
        self.assertEqual(info.version, "2.1.0")
        self.assertTrue(info.is_update_available)
        self.assertIsNotNone(info.source_archive_asset)
        self.assertIsNotNone(info.checksums_asset)
        self.assertEqual(info.source_archive_asset.name, "suscrcpy-source.zip")

    def test_parse_release_json_no_update_available(self) -> None:
        mgr = UpdateManager(current_version="2.1.0")
        mock_data = {
            "tag_name": "v2.1.0",
            "assets": [],
        }
        info = mgr._parse_release_json(mock_data)
        self.assertFalse(info.is_update_available)

    def test_update_aborts_on_checksum_mismatch(self) -> None:
        # Create a mock release with invalid checksum
        archive_path = self.temp_path / "mock_archive.zip"
        with zipfile.ZipFile(archive_path, "w") as z:
            z.writestr("main.py", "print('version 2.0')")

        mock_release = ReleaseInfo(
            tag_name="v2.0.0",
            version="2.0.0",
            name="v2.0.0",
            body="Notes",
            published_at="2026-11-18T10:00:00Z",
            html_url="https://github.com/Shadab-2604/suscrcpy",
            assets={
                "suscrcpy-source.zip": ReleaseAsset("suscrcpy-source.zip", "https://example.com/mock.zip", 100),
                "SHA256SUMS": ReleaseAsset("SHA256SUMS", "https://example.com/SHA256SUMS", 50),
            },
            is_update_available=True,
        )

        with patch.object(self.manager, "download_file") as mock_dl:
            # First call is SHA256SUMS, second is archive
            def fake_download(url, dest, **kwargs):
                if "SHA256SUMS" in str(dest):
                    dest.write_text("0000000000000000000000000000000000000000000000000000000000000000  suscrcpy-source.zip\n")
                else:
                    shutil.copy(archive_path, dest)
                return dest

            mock_dl.side_effect = fake_download

            with self.assertRaises(ChecksumMismatchError):
                self.manager.perform_update(release=mock_release)

        # Ensure installation was not modified
        self.assertIn("version 1.0.0", (self.install_dir / "main.py").read_text())

    def test_rollback_on_failed_verification(self) -> None:
        # Create a mock archive with broken main.py that fails self-test verification
        archive_path = self.temp_path / "mock_archive_broken.zip"
        with zipfile.ZipFile(archive_path, "w") as z:
            z.writestr("main.py", "import non_existent_syntax_error_module_XYZ")

        real_hash = UpdateManager.calculate_sha256(archive_path)

        mock_release = ReleaseInfo(
            tag_name="v2.0.0",
            version="2.0.0",
            name="v2.0.0",
            body="Notes",
            published_at="2026-11-18T10:00:00Z",
            html_url="https://github.com/Shadab-2604/suscrcpy",
            assets={
                "suscrcpy-source.zip": ReleaseAsset("suscrcpy-source.zip", "https://example.com/mock.zip", 100),
                "SHA256SUMS": ReleaseAsset("SHA256SUMS", "https://example.com/SHA256SUMS", 50),
            },
            is_update_available=True,
        )

        with patch.object(self.manager, "download_file") as mock_dl:
            def fake_download(url, dest, **kwargs):
                if "SHA256SUMS" in str(dest):
                    dest.write_text(f"{real_hash}  suscrcpy-source.zip\n")
                else:
                    shutil.copy(archive_path, dest)
                return dest

            mock_dl.side_effect = fake_download

            with self.assertRaises(UpdateError):
                self.manager.perform_update(release=mock_release)

        # Rollback should restore the original working main.py
        self.assertIn("version 1.0.0", (self.install_dir / "main.py").read_text())


if __name__ == "__main__":
    unittest.main()
