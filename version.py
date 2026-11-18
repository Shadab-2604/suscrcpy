"""Single authoritative version metadata for SUSCRCPY."""
from __future__ import annotations

from typing import Tuple

APP_NAME = "SUSCRCPY"
APP_TITLE = "SUSCRCPY — Android Testing & Diagnostics Workstation"
APP_VERSION = "3.0.0"
GITHUB_OWNER = "Shadab-2604"
GITHUB_REPO = "suscrcpy"
GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
API_LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def parse_semver(v_str: str) -> Tuple[int, int, int, int, str]:
    """Parse semantic version string (e.g. 'v2.1.0', '2.1.0', '2.1.0-beta.1') into comparable tuple.

    Returns:
        (major, minor, patch, is_final_release_flag, prerelease_string)
        Note: is_final_release_flag is 1 for final releases, 0 for prereleases,
        so that 2.1.0 > 2.1.0-rc1.
    """
    clean = v_str.strip().lstrip("vV")
    prerelease = ""
    if "-" in clean:
        clean, prerelease = clean.split("-", 1)

    parts = []
    for chunk in clean.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)

    while len(parts) < 3:
        parts.append(0)

    is_final = 1 if not prerelease else 0
    return (parts[0], parts[1], parts[2], is_final, prerelease)


def is_newer_version(remote_v: str, local_v: str = APP_VERSION) -> bool:
    """Check if remote_v is strictly newer than local_v using semantic version comparison."""
    return parse_semver(remote_v) > parse_semver(local_v)
