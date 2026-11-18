"""Installed Android applications discovery and management for SUSCRCPY.

Queries package manager on device, categorizes user vs system applications,
and retrieves version metadata without downloading APKs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from core.adb_manager import AdbManager

logger = logging.getLogger("suscrcpy.app_manager")


@dataclass
class AppInfo:
    """Represents an installed Android application."""
    package_name: str
    app_name: str
    is_system: bool
    version_name: str = "Unknown"
    version_code: str = "Unknown"

    @property
    def category_label(self) -> str:
        return "System" if self.is_system else "User"

    @property
    def display_name(self) -> str:
        return self.app_name if self.app_name else self.package_name


class AppManager(QObject):
    """Manages application retrieval, caching, filtering, and metadata enrichment."""

    apps_loaded = Signal(list)  # list of AppInfo
    app_selected = Signal(object)  # AppInfo

    def __init__(self, adb_manager: AdbManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.adb = adb_manager
        # Cache per device serial
        self._cache: Dict[str, List[AppInfo]] = {}
        self._current_apps: List[AppInfo] = []
        self._selected_app: Optional[AppInfo] = None

    @property
    def current_apps(self) -> List[AppInfo]:
        return self._current_apps

    @property
    def selected_app(self) -> Optional[AppInfo]:
        return self._selected_app

    def load_applications(self, serial: str, force_refresh: bool = False) -> List[AppInfo]:
        """Fetch all installed applications for the device, distinguishing user and system apps."""
        if not force_refresh and serial in self._cache:
            self._current_apps = self._cache[serial]
            self.apps_loaded.emit(self._current_apps)
            return self._current_apps

        logger.info("Scanning installed applications on device %s...", serial)
        try:
            # Query third-party (user) apps
            user_pkgs = set(self.adb.list_packages(serial, filter_type="user"))
            # Query system apps
            system_pkgs = set(self.adb.list_packages(serial, filter_type="system"))
            # Query all apps to catch any edge cases
            all_pkgs = set(self.adb.list_packages(serial, filter_type="all"))
            all_pkgs.update(user_pkgs)
            all_pkgs.update(system_pkgs)

            app_list: List[AppInfo] = []
            for pkg in sorted(all_pkgs):
                is_system = pkg in system_pkgs and pkg not in user_pkgs
                # User-friendly name: use clean tail of package name if no custom label
                tail = pkg.split(".")[-1].replace("_", " ").title()
                app_name = tail

                app_list.append(
                    AppInfo(
                        package_name=pkg,
                        app_name=app_name,
                        is_system=is_system,
                    )
                )

            self._cache[serial] = app_list
            self._current_apps = app_list
            self.apps_loaded.emit(app_list)
            return app_list
        except Exception as e:
            logger.error("Failed to load applications for %s: %s", serial, e)
            self._current_apps = []
            self.apps_loaded.emit([])
            return []

    def enrich_app_details(self, serial: str, app: AppInfo) -> AppInfo:
        """Fetch version information on demand for a selected application."""
        if app.version_name == "Unknown":
            v_name, v_code = self.adb.get_package_version_info(serial, app.package_name)
            app.version_name = v_name
            app.version_code = v_code
        return app

    def select_app(self, app: Optional[AppInfo]) -> None:
        """Set the active application for targeted testing and logging."""
        self._selected_app = app
        self.app_selected.emit(app)

    def launch_app(self, serial: str, package_name: str) -> Tuple[bool, str]:
        """Launch the application's default launcher activity via monkey."""
        try:
            logger.info("Launching package %s on %s...", package_name, serial)
            res = self.adb.run(
                ["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
                serial=serial,
            )
            return True, f"Launched {package_name}"
        except Exception as e:
            logger.error("Failed to launch package %s on %s: %s", package_name, serial, e)
            return False, f"Failed to launch: {e}"

    def force_stop_app(self, serial: str, package_name: str) -> Tuple[bool, str]:
        """Force terminate application process via am force-stop."""
        try:
            logger.info("Force stopping package %s on %s...", package_name, serial)
            self.adb.run(["shell", "am", "force-stop", package_name], serial=serial)
            return True, f"Force-stopped {package_name}"
        except Exception as e:
            logger.error("Failed to force stop %s on %s: %s", package_name, serial, e)
            return False, f"Failed to stop: {e}"

    def get_app_permissions(self, serial: str, package_name: str) -> List[str]:
        """Retrieve granted permissions for the package via dumpsys."""
        permissions: List[str] = []
        try:
            raw = self.adb.run(["shell", "dumpsys", "package", package_name], serial=serial)
            in_perms = False
            for line in raw.splitlines():
                line = line.strip()
                if "grantedPermissions:" in line or "requested permissions:" in line:
                    in_perms = True
                    continue
                if in_perms:
                    if line.startswith("android.permission."):
                        perm = line.split(":")[0].strip()
                        if perm not in permissions:
                            permissions.append(perm)
                    elif line and not line.startswith("android.permission.") and ":" in line:
                        in_perms = False
        except Exception as e:
            logger.debug("Failed to read permissions for %s: %s", package_name, e)
        return permissions

    def filter_apps(
        self,
        apps: List[AppInfo],
        query: str = "",
        category: str = "all",  # "all", "user", "system"
    ) -> List[AppInfo]:
        """Filter application list by search term and category."""
        query = query.lower().strip()
        filtered: List[AppInfo] = []

        for app in apps:
            if category == "user" and app.is_system:
                continue
            if category == "system" and not app.is_system:
                continue

            if query:
                if query not in app.package_name.lower() and query not in app.app_name.lower():
                    continue

            filtered.append(app)

        return filtered
