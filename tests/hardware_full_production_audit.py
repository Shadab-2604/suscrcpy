"""Complete Production Audit & Hardware Test Suite for SUSCRCPY.

Executes end-to-end hardware testing across all modules using the live connected
Android device (0123456789ABCDEF), captures device and desktop UI screenshots,
validates features, and generates an evidence audit report.
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Configure offscreen Qt platform for headless execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6 import QtCore, QtGui, QtWidgets

from core.adb_manager import AdbManager
from core.app_manager import AppManager
from core.device_manager import DeviceManager
from core.event_manager import EventManager
from core.evidence_manager import EvidenceManager
from core.log_manager import LogManager
from core.notes_manager import NotesManager, TestObservation
from core.profile_manager import ProfileManager
from core.proxy_manager import ProxyManager
from core.recording_manager import RecordingManager
from core.report_generator import ReportGenerator
from core.scrcpy_manager import ScrcpyManager
from core.screen_manager import ScreenManager
from core.screenshot_manager import ScreenshotManager
from core.session_manager import SessionManager, SessionStatus
from ui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("suscrcpy.hardware_audit")


class ProductionHardwareAudit:
    """Orchestrates comprehensive hardware and module verification."""

    def __init__(self) -> None:
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["suscrcpy_audit"])
        self.audit_dir = Path("/home/bablu/TOOLS/suscrcpy/docs/screenshots")
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir = Path("/home/bablu/TOOLS/suscrcpy/docs/audit_evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        self.adb = AdbManager()
        self.device_serial = "0123456789ABCDEF"
        self.results: dict[str, bool] = {}
        self.details = None

    def run_all(self) -> bool:
        """Run audit across all 12 core modules."""
        logger.info("=== STARTING SUSCRCPY PRODUCTION HARDWARE AUDIT ===")
        print("\n" + "=" * 60)
        print("   SUSCRCPY v3.0 — PRODUCTION HARDWARE & MODULE AUDIT")
        print("=" * 60)

        self.test_module_1_adb_device()
        self.test_module_2_screen_resolutions()
        self.test_module_3_scrcpy_streaming()
        self.test_module_4_app_manager()
        self.test_module_5_screenshots_and_annotation()
        self.test_module_6_screen_recording()
        self.test_module_7_logcat_streaming()
        self.test_module_8_profiles_library()
        self.test_module_9_proxy_manager()
        self.test_module_10_sessions_and_notes()
        self.test_module_11_evidence_and_reports()
        self.test_module_12_ui_rendering_and_screenshots()

        print("\n" + "=" * 60)
        print("                 AUDIT SUMMARY")
        print("=" * 60)
        all_passed = True
        for mod, status in self.results.items():
            tag = "[ PASS ]" if status else "[ FAIL ]"
            if not status:
                all_passed = False
            print(f" {tag} {mod}")
        print("=" * 60)
        print(f"Final Result: {'100% PRODUCTION READY' if all_passed else 'DEFECTS DETECTED'}\n")
        return all_passed

    def test_module_1_adb_device(self) -> None:
        """Module 1: ADB Manager & Device Details."""
        name = "Module 1: ADB Connection & Hardware Profiling"
        try:
            devs = self.adb.list_devices()
            assert any(d.serial == self.device_serial for d in devs), f"Device {self.device_serial} not in list"
            self.details = self.adb.get_device_details(self.device_serial)
            assert self.details.model, "Missing device model"
            assert self.details.android_version, "Missing Android version"
            assert self.details.physical_resolution == (800, 1280), f"Unexpected physical size: {self.details.physical_resolution}"
            logger.info("Module 1 PASSED: Device %s (Android %s, %s)", self.details.model, self.details.android_version, self.details.physical_resolution)
            self.results[name] = True
        except Exception as e:
            logger.error("Module 1 FAILED: %s", e)
            self.results[name] = False

    def test_module_2_screen_resolutions(self) -> None:
        """Module 2: Screen Manager Resolution & Aspect Ratio Lifecycle."""
        name = "Module 2: Screen Resolution & Aspect Ratio Sync"
        try:
            sm = ScreenManager(self.adb)
            phys, _ = sm.record_initial_resolution(self.device_serial)
            assert phys == (800, 1280), f"Expected physical 800x1280, got {phys}"

            # 1. Apply 800x800 square
            w1, h1 = sm.apply_resolution(self.device_serial, 800, 800, verify=True)
            assert (w1, h1) == (800, 800), f"Failed applying 800x800: got {w1}x{h1}"

            # 2. Reset back to native
            p_reset = sm.reset_resolution(self.device_serial)
            assert p_reset == (800, 1280), f"Reset failed, got {p_reset}"

            # Verify no override remains
            _, ovr = self.adb.get_display_size(self.device_serial)
            assert ovr is None, f"Override still set: {ovr}"

            logger.info("Module 2 PASSED: 800x800 applied, verified, and cleanly reset to 800x1280.")
            self.results[name] = True
        except Exception as e:
            logger.error("Module 2 FAILED: %s", e)
            self.results[name] = False

    def test_module_3_scrcpy_streaming(self) -> None:
        """Module 3: Scrcpy Manager & Texture Sniffing."""
        name = "Module 3: Live Screen Mirroring & Texture Sniffing"
        try:
            sm = ScrcpyManager()
            detected_dims = []
            sm.stream_dimensions_changed.connect(lambda w, h: detected_dims.append((w, h)))

            proc, title = sm.start(self.device_serial, quality_profile="performance")
            assert proc.poll() is None, "scrcpy process died immediately"

            # Wait up to 3 seconds for texture output
            for _ in range(30):
                time.sleep(0.1)
                self.app.processEvents()
                if detected_dims:
                    break

            sm.stop()
            assert len(detected_dims) > 0, "Failed to capture stream texture from scrcpy"
            logger.info("Module 3 PASSED: Stream texture detected %s, stopped cleanly.", detected_dims[0])
            self.results[name] = True
        except Exception as e:
            logger.error("Module 3 FAILED: %s", e)
            self.results[name] = False

    def test_module_4_app_manager(self) -> None:
        """Module 4: Application Discovery & Metadata."""
        name = "Module 4: Installed Application Discovery & Filter"
        try:
            am = AppManager(self.adb)
            apps = am.load_applications(self.device_serial)
            assert len(apps) > 50, f"Expected >50 apps, got {len(apps)}"

            # Search filter test
            settings_apps = am.filter_apps("settings", category="all")
            assert len(settings_apps) > 0, "Failed searching for settings app"

            # Check permissions query
            perms = am.get_app_permissions(self.device_serial, "com.android.settings")
            assert len(perms) > 0, "Failed querying app permissions"

            logger.info("Module 4 PASSED: Loaded %d packages, verified search & permissions.", len(apps))
            self.results[name] = True
        except Exception as e:
            logger.error("Module 4 FAILED: %s", e)
            self.results[name] = False

    def test_module_5_screenshots_and_annotation(self) -> None:
        """Module 5: Screenshot Capture & Vector Annotation."""
        name = "Module 5: Framebuffer Screenshot & Annotation"
        try:
            sm = ScreenshotManager(self.adb)
            meta = sm.capture_screenshot(self.device_serial, destination_dir=self.audit_dir)
            assert meta is not None, "Failed capturing screenshot"
            assert Path(meta.raw_path).exists(), f"Raw screenshot missing: {meta.raw_path}"
            assert meta.width > 0 and meta.height > 0, f"Invalid dimensions: {meta.width}x{meta.height}"

            # Non-destructive annotation
            from PySide6.QtCore import QPoint, QRect
            from PySide6.QtGui import QColor

            ann_path = sm.annotate_screenshot(
                meta=meta,
                rectangles=[(QRect(50, 50, 300, 200), QColor("#EF4444"), 4)],
                texts=[(QPoint(60, 90), "HARDWARE AUDIT VERIFIED", QColor("#10B981"), 18)],
            )
            assert ann_path is not None and ann_path.exists(), "Annotated screenshot missing"

            # Copy sample for docs
            shutil.copy(meta.raw_path, self.audit_dir / "device_raw_capture.png")
            shutil.copy(str(ann_path), self.audit_dir / "device_annotated_capture.png")

            logger.info("Module 5 PASSED: Raw (%dx%d) and annotated screenshots created.", meta.width, meta.height)
            self.results[name] = True
        except Exception as e:
            logger.error("Module 5 FAILED: %s", e)
            self.results[name] = False

    def test_module_6_screen_recording(self) -> None:
        """Module 6: Device Screen Recording."""
        name = "Module 6: Screen Recording & MP4 Finalization"
        try:
            rm = RecordingManager(self.adb)
            rm.start_recording(self.device_serial, destination_dir=self.audit_dir)
            assert rm.is_recording, "Recording manager not active"

            # Record 2.5 seconds
            time.sleep(2.5)
            meta = rm.stop_recording()
            assert meta is not None, "Recording metadata is None"
            assert Path(meta.filepath).exists(), f"MP4 missing: {meta.filepath}"
            assert meta.file_size_bytes > 1000, f"MP4 too small: {meta.file_size_bytes} bytes"
            assert meta.duration_seconds >= 2, f"Expected >=2s, got {meta.duration_seconds}s"

            logger.info("Module 6 PASSED: Captured %ds MP4 (%d bytes).", meta.duration_seconds, meta.file_size_bytes)
            self.results[name] = True
        except Exception as e:
            logger.error("Module 6 FAILED: %s", e)
            self.results[name] = False

    def test_module_7_logcat_streaming(self) -> None:
        """Module 7: Live Logcat Streaming & Diagnostic Parsing."""
        name = "Module 7: Logcat Streaming & Diagnostic Parsing"
        try:
            lm = LogManager(self.adb)
            received = []
            lm.new_logs_batch.connect(lambda entries: received.extend(entries))

            lm.start_capture(self.device_serial)
            for _ in range(15):
                time.sleep(0.1)
                self.app.processEvents()

            lm.stop_capture()
            assert len(received) > 0, "No log entries captured"
            sample = received[0]
            assert sample.level and sample.tag, "LogEntry missing level or tag"

            # Test export
            log_export_path = self.audit_dir / "device_logcat_sample.log"
            with open(log_export_path, "w", encoding="utf-8") as f:
                for entry in received[:100]:
                    f.write(f"{entry.timestamp} {entry.pid} {entry.tid} {entry.level} {entry.tag}: {entry.message}\n")

            logger.info("Module 7 PASSED: Captured %d live log entries, exported sample.", len(received))
            self.results[name] = True
        except Exception as e:
            logger.error("Module 7 FAILED: %s", e)
            self.results[name] = False

    def test_module_8_profiles_library(self) -> None:
        """Module 8: Universal Screen Profiles Library."""
        name = "Module 8: Universal Screen Profiles Database"
        try:
            from core.profile_model import VALID_CATEGORIES
            pm = ProfileManager()
            assert len(VALID_CATEGORIES) >= 12, f"Expected >=12 categories, got {len(VALID_CATEGORIES)}"
            results = pm.search_profiles("Galaxy")
            assert len(results) > 0, "Search for 'Galaxy' returned 0 results"
            logger.info("Module 8 PASSED: %d categories loaded, search verified.", len(VALID_CATEGORIES))
            self.results[name] = True
        except Exception as e:
            logger.error("Module 8 FAILED: %s", e)
            self.results[name] = False

    def test_module_9_proxy_manager(self) -> None:
        """Module 9: Network Proxy Manager."""
        name = "Module 9: Network Proxy Configuration"
        try:
            pm = ProxyManager(self.adb)
            ok_set, msg_set = pm.set_device_proxy(self.device_serial, "10.10.10.1", 8080)
            assert ok_set, f"Failed setting proxy: {msg_set}"
            cfg = pm.get_device_proxy(self.device_serial)
            assert cfg.is_enabled and cfg.host == "10.10.10.1" and cfg.port == 8080

            ok_clr, msg_clr = pm.clear_device_proxy(self.device_serial)
            assert ok_clr, f"Failed clearing proxy: {msg_clr}"
            cfg_clean = pm.get_device_proxy(self.device_serial)
            assert not cfg_clean.is_enabled, "Proxy still enabled after clear"

            logger.info("Module 9 PASSED: Set and cleared HTTP proxy verified.")
            self.results[name] = True
        except Exception as e:
            logger.error("Module 9 FAILED: %s", e)
            self.results[name] = False

    def test_module_10_sessions_and_notes(self) -> None:
        """Module 10: Testing Sessions & Notes."""
        name = "Module 10: Testing Sessions & Defect Notes"
        try:
            ev_mgr = EvidenceManager(base_evidence_dir=self.evidence_dir)
            sess_mgr = SessionManager(evidence_manager=ev_mgr)
            sess = sess_mgr.create_session(
                session_name="Hardware Production Verification",
                project_name="HardwareAudit",
                test_type="Functional & UI/UX Audit",
                tester_name="Senior QA Engineer",
                device_serial=self.device_serial,
                device_model="iKall N15",
            )
            sess_mgr.start_session()
            assert sess_mgr.is_active

            notes_mgr = NotesManager()
            obs = notes_mgr.add_observation(
                title="Hardware Production Verification",
                description="All modules verified against live physical device 0123456789ABCDEF.",
                severity="low",
                category="functional",
            )
            assert obs is not None and obs.obs_id

            ended_sess = sess_mgr.end_session()
            assert ended_sess is not None and ended_sess.status == SessionStatus.COMPLETED.value

            logger.info("Module 10 PASSED: Session %s created, observation logged, completed.", sess.session_id)
            self.results[name] = True
        except Exception as e:
            logger.error("Module 10 FAILED: %s", e)
            self.results[name] = False

    def test_module_11_evidence_and_reports(self) -> None:
        """Module 11: Evidence Manifest & HTML Report Generator."""
        name = "Module 11: Evidence Packaging & HTML Report Generator"
        try:
            ev_mgr = EvidenceManager(base_evidence_dir=self.evidence_dir)
            sess_dir = ev_mgr.init_session_directory("HardwareAudit", "AUDIT-001")

            # Add dummy file to manifest
            test_file = sess_dir / "audit_test.txt"
            test_file.write_text("Audit verified")
            manifest_path, items = ev_mgr.generate_manifest()
            assert manifest_path.exists(), "Manifest JSON not generated"
            assert len(items) > 0, "Manifest empty"

            # Generate HTML report
            sess_mgr = SessionManager(evidence_manager=ev_mgr)
            sess_meta = sess_mgr.create_session(
                session_name="Audit Report Generation",
                project_name="HardwareAudit",
                device_serial=self.device_serial,
                device_model="B610A115",
            )
            report_path = self.audit_dir / "audit_test_report.html"
            ReportGenerator.generate_html_report(
                session=sess_meta,
                output_path=report_path,
                observations=[
                    TestObservation(
                        obs_id="OBS-1",
                        title="Display Ratio Check",
                        description="Aspect ratios verified with zero distortion.",
                        severity="low",
                    )
                ],
                manifest_items=items,
            )
            assert report_path.exists(), "HTML report was not created"
            assert report_path.stat().st_size > 500, "HTML report too small"

            logger.info("Module 11 PASSED: Evidence manifest & HTML report generated.")
            self.results[name] = True
        except Exception as e:
            logger.error("Module 11 FAILED: %s", e)
            self.results[name] = False

    def test_module_12_ui_rendering_and_screenshots(self) -> None:
        """Module 12: Desktop UI Workstation Rendering & Screen Captures."""
        name = "Module 12: Desktop Workstation UI Rendering"
        try:
            # Instantiate MainWindow connected to live device
            win = MainWindow()
            win.resize(1366, 768)
            win.show()
            self.app.processEvents()

            # Set live device details on window
            if self.details:
                win.device_mgr.select_device(self.device_serial)
                self.app.processEvents()

            # 1. Capture Full Main Window
            main_pixmap = win.grab()
            main_shot_path = self.audit_dir / "ui_main_window.png"
            main_pixmap.save(str(main_shot_path))
            assert main_shot_path.exists(), "Failed saving main window screenshot"

            # 2. Capture Screen View with Viewport Canvas & Sync HUD
            screen_pixmap = win.screen_view.grab()
            screen_shot_path = self.audit_dir / "ui_screen_view_hud.png"
            screen_pixmap.save(str(screen_shot_path))

            # 3. Capture Tabbed Workstation Panels
            tab_names = [
                ("ui_device_apps.png", 0),
                ("ui_profiles_library.png", 1),
                ("ui_testing_session.png", 2),
                ("ui_network_proxy.png", 3),
                ("ui_test_notes.png", 4),
                ("ui_evidence_files.png", 5),
            ]
            for filename, tab_idx in tab_names:
                win.right_tabs.setCurrentIndex(tab_idx)
                self.app.processEvents()
                panel = win.right_tabs.currentWidget()
                if panel:
                    p_pix = panel.grab()
                    p_pix.save(str(self.audit_dir / filename))

            # 4. Capture Logs Panel
            logs_pixmap = win.logs_panel.grab()
            logs_shot_path = self.audit_dir / "ui_logs_panel.png"
            logs_pixmap.save(str(logs_shot_path))

            win.close()
            logger.info("Module 12 PASSED: Rendered 9 desktop UI screenshots to %s.", self.audit_dir)
            self.results[name] = True
        except Exception as e:
            logger.error("Module 12 FAILED: %s", e)
            self.results[name] = False


if __name__ == "__main__":
    audit = ProductionHardwareAudit()
    success = audit.run_all()
    sys.exit(0 if success else 1)
