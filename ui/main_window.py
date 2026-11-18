"""Main Application Window for SUSCRCPY 3.0 Testing Workstation.

Unified single-window workstation architecture:
- Left: Embedded interactive scrcpy screen with testing toolbar (Shot, Record, Note, Quality, Fullscreen)
- Right Upper: Tabbed Workstation Panels:
    1. Device & Apps (Display ratios, app search, launch, force stop, info)
    2. Screen Profiles (Universal 12-category screen profile database & preview)
    3. Testing Session (Lifecycle, statistics, and chronological event timeline)
    4. Network & Proxy (HTTP proxy configuration, reachability test, Burp/ZAP guidance)
    5. Test Notes (Defect & observation logging with severity & screenshot links)
    6. Evidence Files (Evidence asset tree, manifest generation, HTML report generator)
- Right Lower: Live Android Logcat with level filters, crash grouping, and disk streaming
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
from core.event_manager import EventManager
from core.evidence_manager import EvidenceManager
from core.log_manager import LogManager
from core.notes_manager import NotesManager
from core.process_manager import ProcessManager
from core.profile_manager import ProfileManager
from core.profile_model import ScreenProfile
from core.proxy_manager import ProxyManager
from core.recording_manager import RecordingManager, RecordingMetadata
from core.scrcpy_manager import ScrcpyError, ScrcpyManager
from core.screen_manager import ScreenManager
from core.screenshot_manager import ScreenshotManager, ScreenshotMetadata
from core.session_manager import SessionManager, SessionMetadata, SessionStatus
from ui.evidence_panel import EvidencePanel
from ui.header_bar import HeaderBar
from ui.logs_panel import LogsPanel
from ui.notes_panel import NotesPanel
from ui.profile_selector import ProfileSelector
from ui.proxy_panel import ProxyPanel
from ui.screen_view import ScreenView
from ui.screenshot_dialog import ScreenshotDialog
from ui.session_panel import SessionPanel
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
    """Unified main desktop workstation window."""

    def __init__(
        self,
        custom_adb: Optional[str] = None,
        custom_scrcpy: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        setup_diagnostic_logger()

        # Core Workstation Managers
        self.adb_mgr = AdbManager(custom_adb_path=custom_adb)
        self.device_mgr = DeviceManager(self.adb_mgr)
        self.screen_mgr = ScreenManager(self.adb_mgr)
        self.scrcpy_mgr = ScrcpyManager(custom_scrcpy_path=custom_scrcpy)
        self.app_mgr = AppManager(self.adb_mgr)
        self.log_mgr = LogManager(self.adb_mgr)
        self.profile_mgr = ProfileManager()

        # New Testing Workstation Managers
        self.event_mgr = EventManager(self)
        self.notes_mgr = NotesManager(self)
        self.proxy_mgr = ProxyManager(self.adb_mgr, self)
        self.evidence_mgr = EvidenceManager(parent=self)
        self.screenshot_mgr = ScreenshotManager(self.adb_mgr, self)
        self.recording_mgr = RecordingManager(self.adb_mgr, self)
        self.session_mgr = SessionManager(self.evidence_mgr, self)

        self._active_serial: Optional[str] = None
        self._active_details: Optional[DeviceDetails] = None
        self._profile_dialog: Optional[QtWidgets.QDialog] = None

        self._build_ui()
        self._connect_signals()

        # Initial device scan & interrupted session check
        QtCore.QTimer.singleShot(250, self._initial_connect)
        QtCore.QTimer.singleShot(600, self._check_interrupted_sessions)

    def _build_ui(self) -> None:
        self.setWindowTitle("SUSCRCPY — Android Testing & Diagnostics Workstation")
        self.resize(1380, 850)
        self.setMinimumSize(1024, 650)
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

        # Left Panel: Live Android Screen Container (Embedded scrcpy + quick toolbar)
        self.screen_view = ScreenView(self.scrcpy_mgr)
        self.screen_view.setMinimumWidth(380)
        self.main_splitter.addWidget(self.screen_view)

        # Right Area: Vertical Splitter (Workstation Tabs on top, Logs on bottom)
        self.right_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.setMinimumWidth(440)

        # Right Upper: Tabbed Workstation Panels
        self.right_tabs = QtWidgets.QTabWidget()
        self.right_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #263345; background-color: #12161F; }
            QTabBar::tab { background: #0B0E14; color: #8DA2BC; padding: 6px 12px; font-weight: 600; font-size: 11px; border: 1px solid #263345; border-bottom: none; }
            QTabBar::tab:selected { background: #18202C; color: #FFF; border-bottom: 2px solid #3B82F6; }
            QTabBar::tab:hover { background: #151C27; color: #E2E8F0; }
        """)

        # Tab 1: Device & Apps
        self.settings_panel = SettingsPanel(self.screen_mgr, self.app_mgr)
        self.right_tabs.addTab(self.settings_panel, "⚙ Device & Apps")

        # Tab 2: Universal Screen Profiles
        self.profile_selector = ProfileSelector(self.profile_mgr)
        self.right_tabs.addTab(self.profile_selector, "📱 Screen Profiles")

        # Tab 3: Testing Session
        self.session_panel = SessionPanel(self.session_mgr, self.event_mgr)
        self.right_tabs.addTab(self.session_panel, "🚀 Testing Session")

        # Tab 4: Network & Proxy
        self.proxy_panel = ProxyPanel(self.proxy_mgr, self.event_mgr)
        self.right_tabs.addTab(self.proxy_panel, "🌐 Network & Proxy")

        # Tab 5: Test Notes & Observations
        self.notes_panel = NotesPanel(self.notes_mgr, self.session_mgr)
        self.right_tabs.addTab(self.notes_panel, "📝 Test Notes")

        # Tab 6: Evidence & Reports
        self.evidence_panel = EvidencePanel(self.evidence_mgr, self.session_mgr, self.notes_mgr)
        self.right_tabs.addTab(self.evidence_panel, "📦 Evidence Files")

        self.right_tabs.setMinimumHeight(280)
        self.right_splitter.addWidget(self.right_tabs)

        # Right Lower: Android Logs Panel
        self.logs_panel = LogsPanel(self.log_mgr)
        self.logs_panel.setMinimumHeight(220)
        self.right_splitter.addWidget(self.logs_panel)

        self.main_splitter.addWidget(self.right_splitter)
        root_layout.addWidget(self.main_splitter, stretch=1)

        # Keyboard shortcut for resetting layout
        self.shortcut_reset_layout = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self)
        self.shortcut_reset_layout.activated.connect(self.reset_layout)

        # Restore saved splitter layout or initialize 50/50 division
        self._restore_or_init_splitter_layout()

    def _connect_signals(self) -> None:
        # Header Bar Signals
        self.header_bar.device_selected.connect(self._on_device_selected)
        self.header_bar.refresh_requested.connect(self._on_refresh_devices)
        self.header_bar.check_updates_requested.connect(self._on_check_updates)
        self.header_bar.reset_layout_requested.connect(self.reset_layout)
        self.header_bar.session_action_requested.connect(self._on_header_session_clicked)

        # Device Manager Signals
        self.device_mgr.selected_device_changed.connect(self._on_device_details_changed)
        self.device_mgr.device_disconnected.connect(self._on_device_disconnected)

        # Left Screen Toolbar Signals
        self.screen_view.screenshot_requested.connect(self._on_capture_screenshot)
        self.screen_view.recording_toggle_requested.connect(self._on_toggle_recording)
        self.screen_view.quick_note_requested.connect(self._on_quick_note)
        self.screen_view.quality_changed.connect(self._on_quality_changed)
        self.screen_view.fullscreen_toggled.connect(self._on_fullscreen_toggled)
        self.screen_view.resync_requested.connect(self._on_resync_requested)
        self.screen_view.reset_resolution_requested.connect(self._on_reset_resolution)

        # Recording Manager Signals
        self.recording_mgr.recording_started.connect(lambda _: self.screen_view.set_recording_state(True, 0))
        self.recording_mgr.recording_tick.connect(lambda sec: self.screen_view.set_recording_state(True, sec))
        self.recording_mgr.recording_completed.connect(self._on_recording_completed)
        self.recording_mgr.recording_failed.connect(lambda err: self._show_error("Recording Failed", err))

        # Screenshot Manager Signals
        self.screenshot_mgr.screenshot_captured.connect(self._on_screenshot_captured)
        self.screenshot_mgr.capture_failed.connect(lambda err: self._show_error("Screenshot Error", err))

        # Settings Panel Signals
        self.settings_panel.apply_resolution_requested.connect(self._on_apply_resolution)
        self.settings_panel.reset_resolution_requested.connect(self._on_reset_resolution)
        self.settings_panel.application_selected.connect(self._on_application_selected)
        self.settings_panel.refresh_apps_requested.connect(self._on_refresh_apps)
        self.settings_panel.open_library_requested.connect(lambda: self.right_tabs.setCurrentWidget(self.profile_selector))

        # Profile Selector Signals
        self.profile_selector.apply_to_device_requested.connect(self._on_profile_applied)

        # Session Manager Signals
        self.session_mgr.session_state_changed.connect(self._on_session_state_changed)

        # Logs Panel Signals
        self.logs_panel.start_requested.connect(self._on_start_logs)
        self.logs_panel.stop_requested.connect(self._on_stop_logs)
        self.logs_panel.clear_device_buffer_requested.connect(self._on_clear_device_buffer)
        self.log_mgr.stats_updated.connect(self._on_log_stats_updated)
        self.log_mgr.crash_alert.connect(self._on_crash_alert)

        # Notes Signals
        self.notes_mgr.observation_added.connect(self._update_metrics)
        self.notes_mgr.observation_deleted.connect(lambda _: self._update_metrics())

    def _initial_connect(self) -> None:
        """Scan for connected devices on startup."""
        self.device_mgr.refresh_devices()

    def _check_interrupted_sessions(self) -> None:
        """Scan for sessions interrupted by previous unexpected shutdowns."""
        interrupted = self.session_mgr.scan_for_interrupted_sessions()
        if interrupted:
            latest = interrupted[0]
            reply = QtWidgets.QMessageBox.question(
                self,
                "Recover Interrupted Session?",
                f"An interrupted testing session was detected:\n\n"
                f"ID: {latest.session_id}\n"
                f"Name: {latest.session_name}\n"
                f"Started: {latest.start_time}\n\n"
                f"Would you like to recover and resume this session?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.session_mgr.recover_session(latest)
                self.right_tabs.setCurrentWidget(self.session_panel)

    def _on_header_session_clicked(self) -> None:
        self.right_tabs.setCurrentWidget(self.session_panel)

    def _on_device_selected(self, serial: str) -> None:
        if serial == self._active_serial:
            return
        self._stop_active_sessions()
        self._active_serial = serial
        self.device_mgr.select_device(serial)
        self.proxy_panel.set_device_serial(serial)

    def _on_device_details_changed(self, details: Optional[DeviceDetails]) -> None:
        self._active_details = details
        self.logs_panel.set_device_details(details)

        if not details:
            self._active_serial = None
            self.screen_view.reset_view()
            self.proxy_panel.set_device_serial(None)
            self.session_panel.set_device_context({})
            return

        serial = details.serial
        self._active_serial = serial
        self.proxy_panel.set_device_serial(serial)
        self.screen_mgr.record_initial_resolution(serial)

        # Context updates
        dev_dict = {
            "serial": details.serial,
            "model": details.model,
            "manufacturer": details.manufacturer,
            "android_version": details.android_version,
            "sdk_level": details.sdk_level,
            "physical_resolution": details.physical_resolution,
            "density": details.density,
        }
        self.session_panel.set_device_context(dev_dict)

        self.event_mgr.record_event(
            category="device",
            action="connected",
            description=f"Device {details.model} ({serial}) connected via ADB",
            device_serial=serial,
        )

        w, h = details.override_resolution or details.physical_resolution
        self.settings_panel.set_current_dimensions(w, h, is_override=bool(details.override_resolution))
        self.screen_view.set_android_dimensions(w, h)
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
            self.event_mgr.record_event(
                category="device",
                action="disconnected",
                description=f"Device {serial} disconnected",
                device_serial=serial,
            )
            # Safe finalize recording if active
            if self.recording_mgr.is_recording:
                self.recording_mgr.stop_recording()

            self._stop_active_sessions()
            self._active_serial = None
            self._active_details = None
            self.screen_view.reset_view()
            self.proxy_panel.set_device_serial(None)
            self._show_warning(
                "Device Disconnected",
                f"Android device '{serial}' was disconnected.\n"
                "Screen mirroring, recordings, and log streaming have been safely stopped.",
            )

    def _stop_active_sessions(self) -> None:
        self.scrcpy_mgr.stop()
        self.log_mgr.stop_capture()
        self.logs_panel.set_streaming_active(False)

    def _on_refresh_devices(self) -> None:
        self.device_mgr.refresh_devices()

    def _on_capture_screenshot(self) -> None:
        """Capture screenshot from live Android screen and display review/annotation dialog."""
        if not self._active_serial:
            self._show_warning("No Device", "Please connect and select an active Android device first.")
            return

        session = self.session_mgr.active_session
        session_id = session.session_id if session else None
        target_pkg = session.target_package if session else None

        dest_dir = self.evidence_mgr.get_subdirectory("screenshots")
        meta = self.screenshot_mgr.capture_screenshot(
            serial=self._active_serial,
            destination_dir=dest_dir,
            session_id=session_id,
            package_name=target_pkg,
        )
        if meta:
            self.event_mgr.record_event(
                category="capture",
                action="screenshot_captured",
                description=f"Device screenshot captured: {Path(meta.raw_path).name}",
                session_id=session_id,
                device_serial=self._active_serial,
                package_name=target_pkg,
            )
            self._update_metrics()

    def _on_screenshot_captured(self, meta: ScreenshotMetadata) -> None:
        """Display annotation/preview dialog for the newly captured screenshot."""
        shots = [s.raw_path for s in self.screenshot_mgr.history]
        self.notes_panel.set_available_screenshots(shots)
        self.evidence_panel.refresh_evidence_tree()

        dlg = ScreenshotDialog(meta, self.screenshot_mgr, parent=self)
        dlg.exec()
        self.evidence_panel.refresh_evidence_tree()

    def _on_toggle_recording(self) -> None:
        """Toggle device screen recording on / off."""
        if not self._active_serial:
            self._show_warning("No Device", "Please connect and select an active Android device first.")
            return

        if self.recording_mgr.is_recording:
            rec_meta = self.recording_mgr.stop_recording()
        else:
            session = self.session_mgr.active_session
            session_id = session.session_id if session else None
            target_pkg = session.target_package if session else None
            dest_dir = self.evidence_mgr.get_subdirectory("recordings")
            ok = self.recording_mgr.start_recording(
                serial=self._active_serial,
                destination_dir=dest_dir,
                session_id=session_id,
                package_name=target_pkg,
            )
            if ok:
                self.event_mgr.record_event(
                    category="recording",
                    action="recording_started",
                    description="Device screen recording started",
                    session_id=session_id,
                    device_serial=self._active_serial,
                    package_name=target_pkg,
                )

    def _on_recording_completed(self, rec: RecordingMetadata) -> None:
        self.screen_view.set_recording_state(False)
        self.event_mgr.record_event(
            category="recording",
            action="recording_stopped",
            description=f"Screen recording finalized: {Path(rec.filepath).name} ({rec.duration_seconds}s)",
            session_id=rec.session_id,
            device_serial=rec.device_serial,
            package_name=rec.package_name,
        )
        self.evidence_panel.refresh_evidence_tree()
        self._update_metrics()
        QtWidgets.QMessageBox.information(
            self, "Recording Completed",
            f"Screen recording saved successfully ({rec.duration_seconds} seconds):\n{Path(rec.filepath).name}"
        )

    def _on_quick_note(self) -> None:
        """Open quick observation dialog."""
        self.right_tabs.setCurrentWidget(self.notes_panel)
        self.notes_panel.prompt_add_observation()

    def _on_quality_changed(self, profile_name: str) -> None:
        """Adjust scrcpy stream quality."""
        self.scrcpy_mgr.set_quality_profile(profile_name)
        if self._active_serial and self.scrcpy_mgr.is_running:
            self.scrcpy_mgr.restart(self._active_serial)

    def _on_fullscreen_toggled(self, is_fs: bool) -> None:
        """Toggle fullscreen mode on window."""
        if is_fs:
            self.showFullScreen()
        else:
            self.showNormal()

    def _on_apply_resolution(self, width: int, height: int) -> None:
        if not self._active_serial:
            self._show_warning("No Device Selected", "Connect and select an authorized device first.")
            return

        try:
            verified_w, verified_h = self.screen_mgr.apply_resolution(self._active_serial, width, height)
            self.settings_panel.set_current_dimensions(verified_w, verified_h, is_override=True)
            self.screen_view.set_android_dimensions(verified_w, verified_h)
            self.scrcpy_mgr.restart(self._active_serial)
            self.event_mgr.record_event(
                category="screen",
                action="resolution_applied",
                description=f"Applied custom display resolution {verified_w}x{verified_h}",
                device_serial=self._active_serial,
            )
        except Exception as e:
            self._show_error("Apply Resolution Error", str(e))

    def _on_reset_resolution(self) -> None:
        if not self._active_serial:
            self._show_warning("No Device Selected", "Connect and select an authorized device first.")
            return

        try:
            phys_res = self.screen_mgr.reset_resolution(self._active_serial)
            self.settings_panel.set_current_dimensions(phys_res[0], phys_res[1], is_override=False)
            self.screen_view.set_android_dimensions(phys_res[0], phys_res[1])
            self.scrcpy_mgr.restart(self._active_serial)
            self.event_mgr.record_event(
                category="screen",
                action="resolution_reset",
                description=f"Reset display resolution to native {phys_res[0]}x{phys_res[1]}",
                device_serial=self._active_serial,
            )
        except Exception as e:
            self._show_error("Reset Resolution Error", str(e))

    def _on_resync_requested(self) -> None:
        """Handle manual re-sync trigger from ScreenView HUD."""
        if not self._active_serial:
            return
        logger.info("Manual re-sync requested for device %s", self._active_serial)
        try:
            phys_res, override_res = self.adb.get_display_size(self._active_serial)
            active_w, active_h = override_res if override_res else phys_res
            self.screen_view.set_android_dimensions(active_w, active_h)
            self.settings_panel.set_current_dimensions(active_w, active_h, is_override=bool(override_res))
            self.scrcpy_mgr.restart(self._active_serial)
            self.event_mgr.record_event(
                category="screen",
                action="resync",
                description=f"Re-synchronized display at {active_w}x{active_h}",
                device_serial=self._active_serial,
            )
        except Exception as e:
            self._show_error("Re-Sync Error", str(e))

    def _on_profile_applied(self, profile: ScreenProfile) -> None:
        """Apply a universal screen profile selected from the library."""
        if not self._active_serial:
            self._show_warning("No Device Selected", "Connect and select an authorized device first.")
            return
        try:
            verified_w, verified_h = self.screen_mgr.apply_resolution(self._active_serial, profile.width, profile.height)
            self.settings_panel.set_current_dimensions(verified_w, verified_h, is_override=True)
            self.screen_view.set_android_dimensions(verified_w, verified_h)
            self.scrcpy_mgr.restart(self._active_serial)
            self.event_mgr.record_event(
                category="screen",
                action="profile_applied",
                description=f"Applied profile: {profile.model_name} ({profile.width}x{profile.height})",
                device_serial=self._active_serial,
            )
            QtWidgets.QMessageBox.information(
                self, "Profile Applied",
                f"Successfully applied screen profile '{profile.model_name}' ({profile.width}x{profile.height}) to device."
            )
        except Exception as e:
            self._show_error("Profile Application Error", str(e))

    def _on_application_selected(self, app: Optional[AppInfo]) -> None:
        if app:
            logger.info("Target application selected: %s (%s)", app.app_name, app.package_name)
            self.session_panel.set_app_context({
                "app_name": app.app_name,
                "package_name": app.package_name,
                "version_name": app.version_name,
                "version_code": app.version_code,
            })
            self.event_mgr.record_event(
                category="app",
                action="selected",
                description=f"Selected target application: {app.display_name} ({app.package_name})",
                package_name=app.package_name,
                device_serial=self._active_serial,
            )
        else:
            self.session_panel.set_app_context(None)

        # Restart log stream with new package target if streaming
        if self._active_serial and self.log_mgr.is_streaming:
            self._on_start_logs()

    def _on_refresh_apps(self) -> None:
        if self._active_serial:
            self.app_mgr.load_applications(self._active_serial, force_refresh=True)

    def _on_session_state_changed(self, meta: Optional[SessionMetadata]) -> None:
        """Synchronize header badge and disk logs with active session."""
        if meta:
            self.header_bar.update_session_badge(meta.session_id, meta.status)
            self._update_metrics()
            # If log capture is running, ensure disk log file is streaming to session folder
            if self._active_serial and self.log_mgr.is_streaming:
                self._on_start_logs()
        else:
            self.header_bar.update_session_badge(None, "")

    def _on_start_logs(self) -> None:
        if not self._active_serial:
            return
        target_pkg = self.settings_panel.selected_package
        disk_log_path = None
        if self.session_mgr.active_session:
            log_folder = self.evidence_mgr.get_subdirectory("logs")
            fname = f"{target_pkg}.log" if target_pkg else "full_device.log"
            disk_log_path = log_folder / fname

        self.log_mgr.start_capture(
            serial=self._active_serial,
            target_package=target_pkg,
            disk_log_path=disk_log_path,
        )
        self.logs_panel.set_streaming_active(True)

    def _on_stop_logs(self) -> None:
        self.log_mgr.stop_capture()
        self.logs_panel.set_streaming_active(False)

    def _on_clear_device_buffer(self) -> None:
        if not self._active_serial:
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear Device Logcat Buffer",
            f"Are you sure you want to clear the hardware logcat buffer on device '{self._active_serial}'?\n\n"
            "This will delete historical logs on the Android device.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.log_mgr.clear_device_buffer(self._active_serial)
            self.event_mgr.record_event(
                category="log",
                action="buffer_cleared",
                description="Hardware logcat buffer cleared via adb logcat -c",
                device_serial=self._active_serial,
            )

    def _on_crash_alert(self, entry) -> None:
        """Record timeline event on confirmed crash."""
        self.event_mgr.record_event(
            category="crash",
            action="crash_detected",
            description=f"CRASH: [{entry.tag}] {entry.message[:70]}",
            device_serial=self._active_serial,
            package_name=self.settings_panel.selected_package,
        )
        self._update_metrics()

    def _on_log_stats_updated(self, err_cnt: int, warn_cnt: int, crash_cnt: int) -> None:
        self._update_metrics()

    def _update_metrics(self, *args) -> None:
        session = self.session_mgr.active_session
        crashes = self.log_mgr._worker._error_detector.crash_count if (self.log_mgr._worker and self.log_mgr._worker._error_detector) else 0
        errors = self.log_mgr._worker._error_detector.error_count if (self.log_mgr._worker and self.log_mgr._worker._error_detector) else 0
        obs = len(self.notes_mgr.observations)
        shots = len(self.screenshot_mgr.history)
        recs = 1 if self.recording_mgr.is_recording else 0
        self.session_panel.update_metrics(crashes, errors, obs, shots, recs)
        if session:
            session.total_crashes = crashes
            session.total_errors = errors
            session.total_observations = obs
            session.total_screenshots = shots

    def _on_check_updates(self) -> None:
        dlg = UpdateDialog(parent=self)
        dlg.exec()

    def reset_layout(self) -> None:
        """Reset splitters to exact 50/50 balance."""
        w = max(self.main_splitter.width(), 1000)
        self.main_splitter.setSizes([w // 2, w // 2])
        h = max(self.right_splitter.height(), 600)
        self.right_splitter.setSizes([h // 2, h // 2])

    def _restore_or_init_splitter_layout(self) -> None:
        """Restore previous session splitter layout from QSettings or enforce 50/50."""
        settings = QtCore.QSettings("SUSCRCPY", "SUSCRCPY-Workstation")
        main_state = settings.value("splitter/main_state")
        right_state = settings.value("splitter/right_state")

        if main_state and isinstance(main_state, QtCore.QByteArray):
            self.main_splitter.restoreState(main_state)
        else:
            QtCore.QTimer.singleShot(50, self.reset_layout)

        if right_state and isinstance(right_state, QtCore.QByteArray):
            self.right_splitter.restoreState(right_state)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Safely restore all hardware overrides, finalize active recordings, and persist settings."""
        # Save splitter states
        settings = QtCore.QSettings("SUSCRCPY", "SUSCRCPY-Workstation")
        settings.setValue("splitter/main_state", self.main_splitter.saveState())
        settings.setValue("splitter/right_state", self.right_splitter.saveState())

        # Finalize any ongoing screen recording
        if self.recording_mgr.is_recording:
            self.recording_mgr.stop_recording()

        # Conclude or save active testing session
        if self.session_mgr.active_session:
            self.session_mgr.save_session()

        # Stop processes
        self.scrcpy_mgr.stop()
        self.log_mgr.stop_capture()

        # Safely restore original physical resolutions
        self.screen_mgr.restore_all()
        ProcessManager.instance().cleanup_all()

        super().closeEvent(event)

    def _show_warning(self, title: str, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, title, message)

    def _show_error(self, title: str, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, title, message)
