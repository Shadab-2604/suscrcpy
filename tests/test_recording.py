"""Unit tests for Screen Recording Manager."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from core.adb_manager import AdbManager
from core.recording_manager import RecordingManager, RecordingMetadata


class TestRecordingManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="suscrcpy_test_rec_"))
        self.mock_adb = MagicMock(spec=AdbManager)
        self.mock_adb.adb_path = "/usr/bin/adb"
        self.rec_mgr = RecordingManager(self.mock_adb)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("subprocess.Popen")
    def test_recording_lifecycle(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        started = self.rec_mgr.start_recording(
            serial="SERIAL123",
            destination_dir=self.temp_dir,
            session_id="SUS-20261118-0001",
            package_name="com.test.app",
        )
        self.assertTrue(started)
        self.assertTrue(self.rec_mgr.is_recording)

        # Mock pulling the finished file
        def fake_pull(args, serial=None):
            # args: ["pull", remote, local]
            local = Path(args[2])
            local.write_bytes(b"FAKE_MP4_BYTES_12345")

        self.mock_adb.run.side_effect = fake_pull

        meta = self.rec_mgr.stop_recording()
        self.assertIsNotNone(meta)
        self.assertFalse(self.rec_mgr.is_recording)
        self.assertEqual(meta.session_id, "SUS-20261118-0001")
        self.assertEqual(meta.package_name, "com.test.app")
        self.assertTrue(Path(meta.filepath).exists())
        self.assertEqual(meta.file_size_bytes, len(b"FAKE_MP4_BYTES_12345"))
        self.assertEqual(len(meta.sha256), 64)


if __name__ == "__main__":
    unittest.main()
