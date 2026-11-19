"""Main window for SUSCRCPY.

Layout: slim header, live Android screen on the left, and a three-tab
workstation on the right (Display, Apps, Logs).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.adb_manager import AdbManager, DeviceDetails
from core.apk_installer import ApkInstaller
from core.app_manager import AppManager
from core.device_manager import DeviceManager
from core.log_manager import LogManager
from core.process_manager import ProcessManager
from core.scrcpy_manager import ScrcpyError, ScrcpyManager
from core.screen_manager import ScreenManager
from core.screenshot_manager import ScreenshotManager
from ui.apps_panel import AppsPanel
from ui.display_panel import DisplayPanel
from ui.header_bar import HeaderBar
from ui.logs_panel import LogsPanel
from ui.screen_view import ScreenView
from ui.styles import DARK_STYLESHEET
from version import APP_TITLE

logger = logging.getLogger("suscrcpy.main_window")


def _diagnostic_log_path() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / "suscrcpy" if sys.platform.startswith("win") else Path.home() / ".suscrcpy"
    return base / "logs" / "diagnostic.log"


def setup_diagnostic_logger() -> None:
    """Write diagnostics to a persistent file next to the user's config."""
    log_file = _diagnostic_log_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"))
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger("suscrcpy")
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    logger.info("Diagnostics: %s", log_file)


def screenshots_directory() -> Path:
    """Pictures/SUSCRCPY on every platform we support."""
    pictures = Path.home() / "Pictures"
    return pictures / "SUSCRCPY"


class MainWindow(QtWidgets.QMainWindow):
    """Single-window Android testing workstation."""

    def __init__(
        self,
        custom_adb: Optional[str] = None,
        custom_scrcpy: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        setup_diagnostic_logger()

        self.adb_mgr = AdbManager(custom_adb_path=custom_adb)
        self.device_mgr = DeviceManager(self.adb_mgr)
        self.screen_mgr = ScreenManager(self.adb_mgr)
        self.scrcpy_mgr = ScrcpyManager(custom_scrcpy_path=custom_scrcpy)
        self.app_mgr = AppManager(self.adb_mgr)
        self.apk_installer = ApkInstaller(self.adb_mgr, self)
        self.log_mgr = LogManager(self.adb_mgr)
        self.screenshot_mgr = ScreenshotManager(self.adb_mgr, self)

        self._active_serial: Optional[str] = None
        self._active_details: Optional[DeviceDetails] = None

        self._build_ui()
        self._connect_signals()

        QtCore.QTimer.singleShot(200, self.device_mgr.refresh_devices)

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 860)
        self.setMinimumSize(1040, 640)
        self.setStyleSheet(DARK_STYLESHEET)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header_bar = HeaderBar(self.device_mgr)
        root.addWidget(self.header_bar)

        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QHBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(8)

        # Left: live screen, right: focused tabs (drag the handle to rebalance)
        self.body_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.body_splitter.setChildrenCollapsible(False)

        self.screen_view = ScreenView(self.scrcpy_mgr)
        self.screen_view.setMinimumWidth(490)
        self.body_splitter.addWidget(self.screen_view)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("workstationTabs")
        self.tabs.setMinimumWidth(380)
        self.body_splitter.addWidget(self.tabs)
        self.body_splitter.setStretchFactor(0, 0)
        self.body_splitter.setStretchFactor(1, 1)
        body_layout.addWidget(self.body_splitter)

        self.display_panel = DisplayPanel(self.screen_mgr)
        self.tabs.addTab(self.display_panel, "Display")

        self.apps_panel = AppsPanel(self.app_mgr, self.apk_installer)
        self.tabs.addTab(self.apps_panel, "Apps")

        self.logs_panel = LogsPanel(self.log_mgr)
        self.tabs.addTab(self.logs_panel, "Logs")

        root.addWidget(body, stretch=1)

        self.statusBar().setSizeGripEnabled(True)
        self.statusBar().showMessage("Ready")

        self._shortcut_fullscreen = QtGui.QShortcut(QtGui.QKeySequence("Escape"), self)
        self._shortcut_fullscreen.activated.connect(self._exit_fullscreen)

    def _connect_signals(self) -> None:
        self.header_bar.device_selected.connect(self.device_mgr.select_device)
        self.header_bar.refresh_requested.connect(self.device_mgr.refresh_devices)
        self.device_mgr.selected_device_changed.connect(self._on_device_changed)
        self.device_mgr.device_disconnected.connect(self._on_device_disconnected)

        self.screen_view.screenshot_requested.connect(self._on_screenshot)
        self.screen_view.quality_changed.connect(self._on_quality_changed)
        self.screen_view.fullscreen_toggled.connect(self._on_fullscreen)
        self.screen_view.resync_requested.connect(self._on_resync)
        self.screen_view.reset_resolution_requested.connect(self._on_reset_resolution)
        self.scrcpy_mgr.stream_dimensions_changed.connect(lambda *_: self._fit_screen_pane())

        self.display_panel.apply_requested.connect(self._on_apply_resolution)
        self.display_panel.reset_requested.connect(self._on_reset_resolution)

        self.apps_panel.application_selected.connect(self._on_app_selected)
        self.apps_panel.refresh_requested.connect(self._on_refresh_apps)
        self.apps_panel.apk_installed.connect(self._on_apk_installed)

        self.logs_panel.start_requested.connect(self._start_logs)
        self.logs_panel.stop_requested.connect(self._stop_logs)
        self.screenshot_mgr.capture_failed.connect(self._on_screenshot_failed)

    # --------------------------------------------------------------- device
    def _on_device_changed(self, details: Optional[DeviceDetails]) -> None:
        self._active_details = details
        self.logs_panel.set_device_details(details)

        if details is None:
            self._active_serial = None
            self.screen_view.reset_view()
            self.display_panel.clear_device()
            self.apps_panel.set_device_serial(None)
            self.statusBar().showMessage("No device selected")
            return

        self._active_serial = details.serial
        self.screen_mgr.record_initial_resolution(details.serial)
        QtCore.QTimer.singleShot(350, self._fit_screen_pane)

        width, height = details.override_resolution or details.physical_resolution
        self.display_panel.set_current_dimensions(
            width, height, is_override=bool(details.override_resolution)
        )
        self.screen_view.set_android_dimensions(width, height)
        self.app_mgr.load_applications(details.serial)
        self.apps_panel.set_device_serial(details.serial)

        self.statusBar().showMessage(
            f"{details.manufacturer} {details.model} \u2014 Android {details.android_version} "
            f"(SDK {details.sdk_level})"
        )

        try:
            self.scrcpy_mgr.start(details.serial)
        except ScrcpyError as exc:
            self._error("Mirror failed", str(exc))

        self._start_logs()

    def _on_device_disconnected(self, serial: str) -> None:
        if serial != self._active_serial:
            return
        logger.warning("Device disconnected: %s", serial)
        self._stop_logs()
        self.scrcpy_mgr.stop()
        self._active_serial = None
        self._active_details = None
        self.screen_view.reset_view()
        self.display_panel.clear_device()
        self.apps_panel.set_device_serial(None)
        self.logs_panel.set_streaming_active(False)

    # -------------------------------------------------------------- display
    def _apply_and_refresh(self, width: int, height: int, failure_title: str) -> None:
        if not self._active_serial:
            self._warn("No device", "Connect and select a device first.")
            return
        self.screen_view.set_updating_state(True, "Applying resolution...")
        try:
            real_w, real_h = self.screen_mgr.apply_resolution(self._active_serial, width, height)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            self.screen_view.set_updating_state(False)
            self._error(failure_title, str(exc))
            return

        self.display_panel.set_current_dimensions(real_w, real_h, is_override=True)
        self.screen_view.set_android_dimensions(real_w, real_h)
        self.scrcpy_mgr.restart(self._active_serial)
        self.statusBar().showMessage(f"Resolution set to {real_w}\u00d7{real_h}")

    def _on_apply_resolution(self, width: int, height: int) -> None:
        self._apply_and_refresh(width, height, "Could not apply resolution")

    def _on_reset_resolution(self) -> None:
        if not self._active_serial:
            self._warn("No device", "Connect and select a device first.")
            return
        self.screen_view.set_updating_state(True, "Restoring native size...")
        try:
            width, height = self.screen_mgr.reset_resolution(self._active_serial)
        except Exception as exc:  # noqa: BLE001
            self.screen_view.set_updating_state(False)
            self._error("Could not reset resolution", str(exc))
            return

        self.display_panel.set_current_dimensions(width, height, is_override=False)
        self.screen_view.set_android_dimensions(width, height)
        self.scrcpy_mgr.restart(self._active_serial)
        self.statusBar().showMessage(f"Native resolution restored ({width}\u00d7{height})")

    def _on_resync(self) -> None:
        if not self._active_serial:
            return
        self.screen_view.set_updating_state(True, "Re-syncing stream...")
        try:
            physical, override = self.screen_mgr.get_active_size(self._active_serial)
        except Exception as exc:  # noqa: BLE001
            self.screen_view.set_updating_state(False)
            self._error("Re-sync failed", str(exc))
            return

        width, height = override or physical
        self.display_panel.set_current_dimensions(width, height, is_override=bool(override))
        self.screen_view.set_android_dimensions(width, height)
        self.scrcpy_mgr.restart(self._active_serial)
        self.statusBar().showMessage(f"Re-synced at {width}\u00d7{height}")

    def _on_quality_changed(self, profile: str) -> None:
        self.scrcpy_mgr.set_quality_profile(profile)
        if self._active_serial:
            self.scrcpy_mgr.restart(self._active_serial)
            self.statusBar().showMessage(f"Stream quality: {profile}")

    def _on_fullscreen(self, enabled: bool) -> None:
        if enabled:
            self.showFullScreen()
        else:
            self.showNormal()

    def _exit_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()

    def _fit_screen_pane(self, retry: bool = True) -> None:
        """Size the left pane to the mirror's real aspect ratio, leaving no dead space."""
        stream_w = self.scrcpy_mgr.stream_width
        stream_h = self.scrcpy_mgr.stream_height
        total = self.body_splitter.width()
        canvas_h = self.screen_view.canvas.height()

        if stream_w <= 0 or stream_h <= 0 or total <= 0 or canvas_h < 200:
            if retry:
                QtCore.QTimer.singleShot(200, lambda: self._fit_screen_pane(retry=False))
            return

        mirror_w = int(round(canvas_h * stream_w / stream_h))
        wanted = mirror_w + 2 * 8 + 16
        left = max(490, min(int(total * 0.62), wanted))
        right = max(380, total - left - self.body_splitter.handleWidth())
        if abs(self.body_splitter.sizes()[0] - left) > 12:
            self.body_splitter.setSizes([left, right])

    # ---------------------------------------------------------------- capture
    def _on_screenshot(self) -> None:
        if not self._active_serial:
            self._warn("No device", "Connect and select a device first.")
            return
        target = screenshots_directory()
        meta = self.screenshot_mgr.capture_screenshot(self._active_serial, target)
        if meta:
            self.statusBar().showMessage(
                f"Screenshot saved: {Path(meta.raw_path).name} ({meta.width}\u00d7{meta.height})",
                8000,
            )

    def _on_screenshot_failed(self, message: str) -> None:
        self._error("Screenshot failed", message)

    # ----------------------------------------------------------------- logs
    def _start_logs(self) -> None:
        if not self._active_serial:
            return
        target = self.apps_panel.selected_package or None
        self.logs_panel.set_target_package(target or "")
        self.log_mgr.start_capture(self._active_serial, target_package=target)
        self.logs_panel.set_streaming_active(True)

    def _stop_logs(self) -> None:
        self.log_mgr.stop_capture()
        self.logs_panel.set_streaming_active(False)

    def _on_app_selected(self, package: str) -> None:
        if not self._active_serial:
            return
        if self.log_mgr.is_streaming:
            self._start_logs()

    def _on_refresh_apps(self) -> None:
        if self._active_serial:
            self.app_mgr.load_applications(self._active_serial, force_refresh=True)

    # ------------------------------------------------------------ install
    def _on_apk_installed(self, apk_name: str) -> None:
        """A fresh install changed the package list and is worth a log line."""
        if self._active_serial:
            self.app_mgr.load_applications(self._active_serial, force_refresh=True)
        self.statusBar().showMessage(f"APK installed: {apk_name}", 8000)
        self.logs_panel.note(f"APK installed from PC: {apk_name}")

    # ---------------------------------------------------------------- close
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._stop_logs()
        self.apk_installer.shutdown()
        self.scrcpy_mgr.stop()
        self.screen_mgr.restore_all()
        ProcessManager.instance().cleanup_all()
        super().closeEvent(event)

    # ------------------------------------------------------------- helpers
    def _warn(self, title: str, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, title, message)

    def _error(self, title: str, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, title, message)
