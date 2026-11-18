"""Unit tests for SUSCRCPY Session Management."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtGui import QGuiApplication

from core.evidence_manager import EvidenceManager
from core.session_manager import SessionManager, SessionStatus


class TestSessionManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QGuiApplication.instance():
            cls.app = QGuiApplication([])

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="suscrcpy_test_sessions_"))
        self.evidence_mgr = EvidenceManager(base_evidence_dir=self.temp_dir)
        self.session_mgr = SessionManager(self.evidence_mgr)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_session_id_format(self):
        sid = self.session_mgr.generate_session_id()
        self.assertTrue(sid.startswith("SUS-"))
        parts = sid.split("-")
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[1]), 8)  # YYYYMMDD
        self.assertEqual(len(parts[2]), 4)  # 0001

    def test_session_lifecycle_and_persistence(self):
        meta = self.session_mgr.create_session(
            session_name="Login Flow Verification",
            project_name="FintechApp",
            test_type="Security Testing",
            tester_name="Alice QA",
            tester_notes="Testing biometric login failure handling",
            device_serial="DEVICE123",
            device_model="Pixel 6",
            device_manufacturer="Google",
            android_version="13",
            sdk_version="33",
            target_app_name="BankApp",
            target_package="com.example.bank",
        )
        self.assertEqual(meta.status, SessionStatus.CREATED.value)
        self.assertEqual(meta.project_name, "FintechApp")

        session_file = self.evidence_mgr.current_session_dir / "session.json"
        self.assertTrue(session_file.exists())

        # Start session
        self.session_mgr.start_session()
        self.assertEqual(self.session_mgr.active_session.status, SessionStatus.RUNNING.value)

        # Pause session
        self.session_mgr.pause_session()
        self.assertEqual(self.session_mgr.active_session.status, SessionStatus.PAUSED.value)

        # Resume session
        self.session_mgr.resume_session()
        self.assertEqual(self.session_mgr.active_session.status, SessionStatus.RUNNING.value)

        # Conclude session
        ended = self.session_mgr.end_session()
        self.assertEqual(ended.status, SessionStatus.COMPLETED.value)
        self.assertIsNotNone(ended.end_time)

        # Verify disk contents
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["status"], SessionStatus.COMPLETED.value)
        self.assertEqual(data["target_package"], "com.example.bank")

    def test_interrupted_session_detection_and_recovery(self):
        # Create a session that gets left in RUNNING status (simulating unexpected shutdown)
        meta = self.session_mgr.create_session(
            session_name="Crash Recovery Test",
            project_name="InterruptedProject",
        )
        self.session_mgr.start_session()

        # Simulate fresh app startup scanning the directory
        new_evidence_mgr = EvidenceManager(base_evidence_dir=self.temp_dir)
        new_session_mgr = SessionManager(new_evidence_mgr)

        interrupted_sessions = new_session_mgr.scan_for_interrupted_sessions()
        self.assertEqual(len(interrupted_sessions), 1)
        self.assertEqual(interrupted_sessions[0].session_id, meta.session_id)
        self.assertEqual(interrupted_sessions[0].status, SessionStatus.INTERRUPTED.value)

        # Recover
        new_session_mgr.recover_session(interrupted_sessions[0])
        self.assertEqual(new_session_mgr.active_session.session_id, meta.session_id)
        self.assertEqual(new_session_mgr.active_session.status, SessionStatus.PAUSED.value)


if __name__ == "__main__":
    unittest.main()
