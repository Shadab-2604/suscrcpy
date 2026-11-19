"""Screenshot capture tests."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6 import QtCore, QtGui, QtWidgets

from core.adb_manager import AdbManager
from core.screenshot_manager import ScreenshotManager


def _png_bytes(width: int = 400, height: int = 800) -> bytes:
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB32)
    image.fill(QtGui.QColor("#1E293B"))
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


class TestScreenshotManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="suscrcpy_shots_"))
        self.adb = MagicMock(spec=AdbManager)
        self.adb.adb_path = "/usr/bin/adb"
        self.manager = ScreenshotManager(self.adb)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_capture_writes_png_with_real_dimensions(self):
        self.manager._read_png = MagicMock(return_value=_png_bytes(400, 800))

        meta = self.manager.capture_screenshot("SERIAL", self.temp_dir)

        self.assertIsNotNone(meta)
        self.assertTrue(Path(meta.raw_path).exists())
        self.assertEqual((meta.width, meta.height), (400, 800))
        self.assertGreater(meta.file_size_bytes, 0)
        self.assertEqual(len(meta.sha256), 64)
        self.assertEqual(len(self.manager.history), 1)

    def test_capture_failure_is_reported(self):
        self.manager._read_png = MagicMock(return_value=b"")
        received = []
        self.manager.capture_failed.connect(received.append)

        meta = self.manager.capture_screenshot("SERIAL", self.temp_dir)

        self.assertIsNone(meta)
        self.assertEqual(len(received), 1)
        self.assertEqual(list(self.temp_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
