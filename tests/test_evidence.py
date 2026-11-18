"""Unit tests for Evidence Manager and SHA-256 Manifest generation."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.evidence_manager import EvidenceManager


class TestEvidenceManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="suscrcpy_test_evidence_"))
        self.evidence_mgr = EvidenceManager(base_evidence_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_directory_hierarchy_initialization(self):
        session_dir = self.evidence_mgr.init_session_directory("Ecommerce", "SUS-20261118-0001")
        self.assertTrue(session_dir.exists())

        expected_subs = ["screenshots", "recordings", "logs", "notes", "events", "reports", "exports"]
        for sub in expected_subs:
            self.assertTrue((session_dir / sub).is_dir())

    def test_manifest_generation_and_checksums(self):
        session_dir = self.evidence_mgr.init_session_directory("Fintech", "SUS-20261118-0002")

        # Create some mock evidence files
        file1 = session_dir / "screenshots" / "screenshot_01.png"
        file1.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00TEST_IMAGE_DATA")

        file2 = session_dir / "logs" / "full_device.log"
        file2.write_text("11-18 12:00:00.000 100 100 I Tag: Message\n", encoding="utf-8")

        manifest_path, items = self.evidence_mgr.generate_manifest()
        self.assertTrue(manifest_path.exists())
        self.assertEqual(len(items), 2)

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_json = json.load(f)

        self.assertEqual(manifest_json["total_files"], 2)
        paths = [item["relative_path"] for item in manifest_json["files"]]
        self.assertIn("screenshots/screenshot_01.png", paths)
        self.assertIn("logs/full_device.log", paths)

        # Verify SHA-256 validity
        for item in manifest_json["files"]:
            self.assertEqual(len(item["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
