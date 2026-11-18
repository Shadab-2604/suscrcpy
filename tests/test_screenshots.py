"""Unit tests for Screenshot Capture and Annotation."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QCoreApplication, QPoint, QRect
from PySide6.QtGui import QColor, QImage

from core.adb_manager import AdbManager
from core.screenshot_manager import ScreenshotManager, ScreenshotMetadata


class TestScreenshotManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtGui import QGuiApplication
        if not QGuiApplication.instance():
            cls.app = QGuiApplication([])

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="suscrcpy_test_shots_"))
        self.mock_adb = MagicMock(spec=AdbManager)
        self.mock_adb.adb_path = "/usr/bin/adb"
        self.shot_mgr = ScreenshotManager(self.mock_adb)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_dummy_png(self, path: Path, width: int = 400, height: int = 800) -> None:
        img = QImage(width, height, QImage.Format.Format_RGB32)
        img.fill(QColor("#1E293B"))
        img.save(str(path), "PNG")

    def test_non_destructive_annotation(self):
        raw_path = self.temp_dir / "screenshot_20261118_120000.png"
        self._create_dummy_png(raw_path)

        meta = ScreenshotMetadata(
            id="SHOT-20261118_120000",
            raw_path=str(raw_path),
            width=400,
            height=800,
            file_size_bytes=raw_path.stat().st_size,
        )

        rectangles = [(QRect(20, 20, 100, 50), QColor("#EF4444"), 3)]
        arrows = [(QPoint(50, 150), QPoint(150, 150), QColor("#F59E0B"), 3)]
        texts = [(QPoint(20, 100), "Bug Note", QColor("#FFFFFF"), 14)]
        blurs = [QRect(20, 200, 80, 40)]

        annotated_path = self.shot_mgr.annotate_screenshot(
            meta,
            rectangles=rectangles,
            arrows=arrows,
            texts=texts,
            blur_regions=blurs,
        )

        self.assertIsNotNone(annotated_path)
        self.assertTrue(annotated_path.exists())
        self.assertTrue(raw_path.exists())  # Raw file preserved intact
        self.assertTrue(annotated_path.name.endswith("_annotated.png"))
        self.assertEqual(meta.annotated_path, str(annotated_path))

        # Verify annotated image validity
        res_img = QImage(str(annotated_path))
        self.assertFalse(res_img.isNull())
        self.assertEqual(res_img.width(), 400)
        self.assertEqual(res_img.height(), 800)


if __name__ == "__main__":
    unittest.main()
