"""Main Application Window for SUSCRCPY Desktop Application.

Unified single-window layout matching the wireframe:
------------------------------------------------------------
| SUSCRCPY        [ Connected Android Device ▼ ]           |
------------------------------------------------------------
|                         |                                  |
|                         |   SCREEN / APP SETTINGS          |
|                         |                                  |
|     LIVE ANDROID        |----------------------------------|
|     SCREEN              |                                  |
|                         |   ANDROID LOGS                   |
|                         |                                  |
|                         |                                  |
------------------------------------------------------------
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.adb_manager import AdbDeviceError, AdbError, AdbManager, DeviceDetails
from core.app_manager import AppInfo, AppManager
from core.device_manager import ConnectionState, DeviceManager
from core.log_manager import LogManager
from core.process_manager import ProcessManager
from core.profile_manager import ProfileManager
from core.profile_model import ScreenProfile
from core.scrcpy_manager import ScrcpyError, ScrcpyManager
from core.screen_manager import ScreenManager
from ui.header_bar import HeaderBar
from ui.logs_panel import LogsPanel
from ui.profile_selector import ProfileSelector
from ui.screen_view import ScreenView
from ui.settings_panel import SettingsPanel
from ui.styles import DARK_STYLESHEET
from ui.update_dialog import UpdateDialog

logger = logging.getLogger("suscrcpy.main_window")


def setup_diagnostic_logger() -> None:
    """Initialize persistent diagnostic log file in user's application directory."""
    if sys.platform.startswith("win"):
        base_dir = Path(os.environ.get("APPDATA", Path.home())) / "suscrcpy"
    else:
        base_dir = Path.home() / ".suscrcpy"

    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "diagnostic.log"

    handler = logging.FileHandler(log_file, encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger("suscrcpy")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    logger.info("SUSCRCPY diagnostic logging initialized: %s", log_file)


class MainWindow(QtWidgets.QMainWindow):
    """Unified main desktop window combining live scrcpy mirror, settings, and logs."""

    def __init__(
        self,
        custom_adb: Optional[str] = None,
        custom_scrcpy: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        setup_diagnostic_logger()

        # Core Managers
        self.adb_mgr = AdbManager(custom_adb_path=custom_adb)
        self.device_mgr = DeviceManager(self.adb_mgr)
        self.screen_mgr = ScreenManager(self.adb_mgr)
        self.scrcpy_mgr = ScrcpyManager(custom_scrcpy_path=custom_scrcpy)
        self.app_mgr = AppManager(self.adb_mgr)
        self.log_mgr = LogManager(self.adb_mgr)
        self.profile_mgr = ProfileManager()

        self._active_serial: Optional[str] = None
        self._active_details: Optional[DeviceDetails] = None
        self._profile_dialog: Optional[QtWidgets.QDialog] = None

        self._build_ui()
        self._connect_signals()

        # Initial device scan
        QtCore.QTimer.singleShot(250, self._initial_connect)

    def _build_ui(self) -> None:
        self.setWindowTitle("SUSCRCPY — Android Device Testing Desktop Application")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)
        self.setStyleSheet(DARK_STYLESHEET)

        # Central Root Container
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QtWidgets.QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Header Bar (Slim horizontal header ~48px)
        self.header_bar = HeaderBar(self.device_mgr)
        root_layout.addWidget(self.header_bar)

        # 2. Main Content Splitter (Horizontal: Left = ScreenView, Right = Vertical Splitter)
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setContentsMargins(6, 6, 6, 6)

        # Left Panel: Live Android Screen Container (Embedded scrcpy)
        self.screen_view = ScreenView(self.scrcpy_mgr)
        self.main_splitter.addWidget(self.screen_view)

        # Right Area: Vertical Splitter (Settings on top, Logs on bottom)
        self.right_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.right_splitter.setChildrenCollapsible(False)

        # Right Upper: Screen and Application Settings Panel
        self.settings_panel = SettingsPanel(self.screen_mgr, self.app_mgr)
        self.right_splitter.addWidget(self.settings_panel)

        # Right Lower: Android Logs Panel
        self.logs_panel = LogsPanel(self.log_mgr)
        self.right_splitter.addWidget(self.logs_panel)

        # Set vertical proportions (Settings ~36%, Logs ~64%)
        self.right_splitter.setStretchFactor(0, 36)
        self.right_splitter.setStretchFactor(1, 64)

        self.main_splitter.addWidget(self.right_splitter)

        # Set horizontal proportions (ScreenView ~43%, Controls ~57%)
        self.main_splitter.setStretchFactor(0, 43)
        self.main_splitter.setStretchFactor(1, 57)

        root_layout.addWidget(self.main_splitter, stretch=1)

    def _connect_signals(self) -> None:
        # Header Bar Signals
        self.header_bar.device_selected.connect(self._on_device_selected)
        self.header_bar.refresh_requested.connect(self._on_refresh_devices)
        self.header_bar.check_updates_requested.connect(self._on_check_updates)

        # Device Manager Signals
        self.device_mgr.selected_device_changed.connect(self._on_device_details_changed)
        self.device_mgr.device_disconnected.connect(self._on_device_disconnected)

        # Settings Panel Signals
        self.settings_panel.apply_resolution_requested.connect(self._on_apply_resolution)
        self.settings_panel.reset_resolution_requested.connect(self._on_reset_resolution)
        self.settings_panel.application_selected.connect(self._on_application_selected)
        self.settings_panel.refresh_apps_requested.connect(self._on_refresh_apps)
        self.settings_panel.open_library_requested.connect(self._on_open_profile_library)

        # Logs Panel Signals
        self.logs_panel.start_requested.connect(self._on_start_logs)
        self.logs_panel.stop_requested.connect(self._on_stop_logs)
        self.logs_panel.clear_device_buffer_requested.connect(self._on_clear_device_buffer)

    def _initial_connect(self) -> None:
        """Scan for connected devices on startup."""
        self.device_mgr.refresh_devices()

    def _on_device_selected(self, serial: str) -> None:
        if serial == self._active_serial:
            return
        self._stop_active_sessions()
        self._active_serial = serial
        self.device_mgr.select_device(serial)

    def _on_device_details_changed(self, details: Optional[DeviceDetails]) -> None:
        self._active_details = details
        self.logs_panel.set_device_details(details)

        if not details:
            self._active_serial = None
            self.screen_view.reset_view()
            return

        serial = details.serial
        self._active_serial = serial
        self.screen_mgr.record_initial_resolution(serial)

        w, h = details.override_resolution or details.physical_resolution
        self.settings_panel.set_current_dimensions(w, h, is_override=bool(details.override_resolution))
        self.app_mgr.load_applications(serial)

        # Start live scrcpy mirror
        try:
            self.scrcpy_mgr.start(serial)
        except ScrcpyError as e:
            self._show_error("scrcpy Startup Error", str(e))

        # Start real-time logs
        self._on_start_logs()

    def _on_device_disconnected(self, serial: str) -> None:
        logger.warning("Device disconnected: %s", serial)
        if self._active_serial == serial:
            self._stop_active_sessions()
            self._active_serial = None
            self._active_details = None
            self.screen_view.reset_view()
            self._show_warning(
                "Device Disconnected",
                f"Android device '{serial}' was disconnected.\n"
                "Screen mirroring and log streaming have been safely stopped.",
            )

    def _stop_active_sessions(self) -> None:
        self.scrcpy_mgr.stop()
        self.log_mgr.stop_capture()
        self.logs_panel.set_streaming_active(False)

    def _on_refresh_devices(self) -> None:
        self.device_mgr.refresh_devices()

    def _on_apply_resolution(self, width: int, height: int) -> None:
        if not self._active_serial:
            self._show_warning("No Device Selected", "Connect and select an authorized device first.")
            return

        try:
            self.screen_mgr.apply_resolution(self._active_serial, width, height)
            self.settings_panel.set_current_dimensions(width, height, is_override=True)
            self.scrcpy_mgr.restart(self._active_serial)
        except Exception as e:
            self._show_error("Apply Resolution Error", str(e))

    def _on_reset_resolution(self) -> None:
        if not self._active_serial:
            self._show_warning("No Device Selected", "Connect and select an authorized device first.")
            return

        try:
            phys_w, phys_h = self.screen_mgr.reset_resolution(self._active_serial)
            self.settings_panel.set_current_dimensions(phys_w, phys_h, is_override=False)
            self.scrcpy_mgr.restart(self._active_serial)
            QtWidgets.QMessageBox.information(
                self,
                "Resolution Reset",
                f"Android native physical resolution restored: {phys_w} × {phys_h} px",
            )
        except Exception as e:
            self._show_error("Reset Resolution Error", str(e))

    def _on_application_selected(self, package_name: str) -> None:
        """Route target package selection to the logs panel."""
        self.logs_panel.set_target_package(package_name if package_name else None)
        # Restart logcat with package target if active
        if self.log_mgr.is_streaming:
            self._on_start_logs()

    def _on_refresh_apps(self) -> None:
        if self._active_serial:
            self.app_mgr.load_applications(self._active_serial, force_refresh=True)

    def _on_open_profile_library(self) -> None:
        """Open the Universal Screen Profiles Library in a dialog window."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Universal Screen Profiles Library")
        dialog.resize(880, 560)
        dialog_layout = QtWidgets.QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(8, 8, 8, 8)

        selector = ProfileSelector(self.profile_mgr, parent=dialog)
        dialog_layout.addWidget(selector)

        def handle_apply(profile: ScreenProfile) -> None:
            dialog.accept()
            w, h = profile.resolution.width_px, profile.resolution.height_px
            self._on_apply_resolution(w, h)

        selector.apply_to_device_requested.connect(handle_apply)
        dialog.exec()

    def _on_check_updates(self) -> None:
        """Open the software update dialog."""
        dialog = UpdateDialog(parent=self)
        dialog.exec()

    def _on_start_logs(self) -> None:
        if not self._active_serial:
            return
        mode = self.logs_panel.get_selected_mode()
        target_pkg = self.logs_panel._target_package if mode == "app" else None
        self.log_mgr.start_capture(self._active_serial, target_package=target_pkg)
        self.logs_panel.set_streaming_active(True)

    def _on_stop_logs(self) -> None:
        self.log_mgr.stop_capture()
        self.logs_panel.set_streaming_active(False)

    def _on_clear_device_buffer(self) -> None:
        if not self._active_serial:
            return
        try:
            self.log_mgr.clear_device_buffer(self._active_serial)
            QtWidgets.QMessageBox.information(
                self, "Buffer Cleared", "Hardware Android logcat buffer cleared successfully."
            )
        except Exception as e:
            self._show_error("Clear Buffer Error", str(e))

    def _show_error(self, title: str, message: str) -> None:
        logger.error("%s: %s", title, message)
        QtWidgets.QMessageBox.critical(self, title, message)

    def _show_warning(self, title: str, message: str) -> None:
        logger.warning("%s: %s", title, message)
        QtWidgets.QMessageBox.warning(self, title, message)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        logger.info("Closing SUSCRCPY application...")
        self._stop_active_sessions()
        self.screen_mgr.restore_all()
        ProcessManager.instance().cleanup_all()
        event.accept()
