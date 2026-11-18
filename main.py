#!/usr/bin/env python3
"""SUSCRCPY: Android Device Testing Desktop Application.

Combines live interactive scrcpy screen mirroring, display aspect ratio management,
installed package discovery, real-time Android log monitoring, and GitHub updates.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure Qt uses xcb platform plugin on Linux when DISPLAY is present so foreign scrcpy
# window reparenting (QWindow.fromWinId) succeeds under X11 and XWayland.
if sys.platform.startswith("linux") and "DISPLAY" in os.environ:
    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "xcb"

from version import APP_NAME, APP_TITLE, APP_VERSION


def setup_console_logging(debug: bool = False) -> None:
    """Configure terminal logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%H:%M:%S",
    )


def configure_platform_environment() -> None:
    """Configure display server and Qt platform settings for best window embedding."""
    if sys.platform.startswith("linux") and "DISPLAY" in os.environ:
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            os.environ["QT_QPA_PLATFORM"] = "xcb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"{APP_TITLE} (v{APP_VERSION})"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )
    parser.add_argument(
        "--check-updates",
        action="store_true",
        help="Check GitHub for latest available release and exit",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Download, verify and install the latest GitHub release (requires sudo for /opt)",
    )
    parser.add_argument(
        "--adb",
        metavar="PATH",
        help="Custom path to the adb binary",
        default=None,
    )
    parser.add_argument(
        "--scrcpy",
        metavar="PATH",
        help="Custom path to the scrcpy binary",
        default=None,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def run_cli_check_updates() -> int:
    """Check GitHub for new releases from the command line."""
    from update_manager import UpdateManager

    print(f"=== {APP_NAME} Update Checker ===")
    print(f"Installed version: {APP_VERSION}")
    print("Checking GitHub repository for latest release...")

    mgr = UpdateManager(current_version=APP_VERSION)
    try:
        release = mgr.fetch_latest_release()
        print(f"Latest version:    {release.version} (Tag: {release.tag_name})")
        print(f"Release URL:       {release.html_url}")

        if release.is_update_available:
            print(f"\n[+] An update is available: v{release.version}")
            print(f"    Release: {release.name}")
            print("\nTo update now, execute:")
            print("    sudo suscrcpy --update\n")
        else:
            print(f"\n[✓] {APP_NAME} is up to date (version {APP_VERSION}).")
        return 0
    except Exception as e:
        print(f"\n[-] Error checking for updates: {e}", file=sys.stderr)
        return 1


def run_cli_update() -> int:
    """Execute update lifecycle from command line."""
    from update_manager import ChecksumMismatchError, PermissionRequiredError, UpdateManager

    print(f"=== {APP_NAME} Automatic Updater ===")
    print(f"Current version: {APP_VERSION}")

    mgr = UpdateManager(current_version=APP_VERSION)
    try:
        def console_progress(status: str, pct: float) -> None:
            pct_int = int(pct * 100)
            print(f"[{pct_int:3d}%] {status}")

        result_msg = mgr.perform_update(progress_callback=console_progress)
        print(f"\n[✓] {result_msg}")
        return 0
    except PermissionRequiredError as pe:
        print(f"\n[-] Permission denied: {pe}", file=sys.stderr)
        return 1
    except ChecksumMismatchError as cme:
        print(f"\n[!] Integrity verification failed: {cme}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[-] Update failed: {e}", file=sys.stderr)
        return 1


def main() -> int:
    args = parse_args()

    # Handle pure CLI flags before launching Qt
    if args.check_updates:
        return run_cli_check_updates()

    if args.update:
        return run_cli_update()

    setup_console_logging(args.debug)
    configure_platform_environment()

    # Create Qt Application
    from PySide6 import QtWidgets
    from ui.main_window import MainWindow

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)

    window = MainWindow(custom_adb=args.adb, custom_scrcpy=args.scrcpy)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
