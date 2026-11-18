"""Unit tests for HTML Report Generator."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from core.event_manager import TimelineEvent
from core.notes_manager import TestObservation
from core.report_generator import ReportGenerator
from core.screenshot_manager import ScreenshotMetadata
from core.session_manager import SessionMetadata


class TestReportGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="suscrcpy_test_reports_"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_html_report_content(self):
        session = SessionMetadata(
            session_id="SUS-20261118-9999",
            session_name="Automated Test Run",
            project_name="DemoProject",
            test_type="Regression Testing",
            tester_name="QA Lead",
            tester_notes="Comprehensive report generation verification",
            device_serial="DEVICE999",
            device_model="iKall N15",
            device_manufacturer="iKall",
            android_version="11",
            sdk_version="30",
            screen_dimensions=(800, 1280),
            display_density=210,
            target_app_name="TestApp",
            target_package="com.example.test",
        )

        obs = [
            TestObservation(
                obs_id="OBS-20261118-001",
                title="NullPointer on Checkout",
                description="Clicking checkout without address triggers unhandled exception",
                severity="Critical",
                category="Crash",
                expected_result="Validation error displayed",
                actual_result="Application crashes to desktop",
            )
        ]

        timeline = [
            TimelineEvent(
                event_id="EVT-001",
                category="session",
                action="started",
                description="Testing session started",
            ),
            TimelineEvent(
                event_id="EVT-002",
                category="crash",
                action="crash_detected",
                description="CRASH: FATAL EXCEPTION in main thread",
            ),
        ]

        shots = [
            ScreenshotMetadata(
                id="SHOT-001",
                raw_path="/fake/path/screenshot_01.png",
                width=800,
                height=1280,
                file_size_bytes=45000,
                sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            )
        ]

        out_path = self.temp_dir / "session_report.html"
        ReportGenerator.generate_html_report(
            session=session,
            output_path=out_path,
            observations=obs,
            timeline=timeline,
            screenshots=shots,
            log_errors_sample=["E/AndroidRuntime: FATAL EXCEPTION: main"],
        )

        self.assertTrue(out_path.exists())
        content = out_path.read_text(encoding="utf-8")

        # Verify key sections are present
        self.assertIn("SUS-20261118-9999", content)
        self.assertIn("NullPointer on Checkout", content)
        self.assertIn("Critical", content)
        self.assertIn("iKall N15", content)
        self.assertIn("com.example.test", content)
        self.assertIn("Chronological Event Timeline", content)
        self.assertIn("Critical Error & Crash Logcat Excerpts", content)


if __name__ == "__main__":
    unittest.main()
