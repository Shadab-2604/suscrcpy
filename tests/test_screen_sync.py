"""Viewport geometry: the mirror stays left-anchored and undistorted for every ratio."""
import unittest

from PySide6 import QtWidgets

from core.screen_manager import ASPECT_RATIOS
from ui.screen_view import CANVAS_PADDING, ViewportCanvas


class TestViewportGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _canvas(self, width: int, height: int, mode: str = "fit") -> ViewportCanvas:
        canvas = ViewportCanvas()
        canvas.set_display_mode(mode)
        canvas.resize(width, height)
        return canvas

    def test_portrait_stream_is_left_anchored(self):
        canvas = self._canvas(1200, 800)
        canvas.set_target_dimensions(720, 1280)
        rect, scale = canvas.fitted_rect()

        self.assertEqual(rect.height(), 800 - 2 * CANVAS_PADDING)
        self.assertEqual(rect.width(), round(rect.height() * 720 / 1280))
        self.assertEqual(rect.x(), CANVAS_PADDING, "portrait mirror must sit on the left")
        self.assertLess(scale, 1.0)

    def test_landscape_stream_is_left_anchored(self):
        canvas = self._canvas(800, 1200)
        canvas.set_target_dimensions(1920, 1080)
        rect, _ = canvas.fitted_rect()

        self.assertEqual(rect.width(), 800 - 2 * CANVAS_PADDING)
        self.assertEqual(rect.x(), CANVAS_PADDING, "landscape mirror must sit on the left")
        self.assertGreater(rect.y(), 0, "landscape mirror should be vertically centred")

    def test_every_ratio_fits_and_keeps_aspect(self):
        canvas = self._canvas(680, 768)
        avail_w, avail_h = 680 - 2 * CANVAS_PADDING, 768 - 2 * CANVAS_PADDING

        for name, (long_factor, short_factor) in ASPECT_RATIOS.items():
            for width, height in (
                (short_factor * 100, long_factor * 100),   # portrait
                (long_factor * 100, short_factor * 100),   # landscape
            ):
                canvas.set_target_dimensions(width, height)
                rect, _ = canvas.fitted_rect()

                self.assertLessEqual(rect.width(), avail_w, f"{name} overflows horizontally")
                self.assertLessEqual(rect.height(), avail_h, f"{name} overflows vertically")
                self.assertEqual(rect.x(), CANVAS_PADDING, f"{name} is not left anchored")
                self.assertGreaterEqual(rect.y(), CANVAS_PADDING, f"{name} clips the top")
                self.assertLessEqual(rect.bottom(), 768 - CANVAS_PADDING, f"{name} clips the bottom")

                rendered = rect.width() / rect.height()
                expected = width / height
                self.assertAlmostEqual(rendered, expected, delta=0.01, msg=f"{name} distorted")

    def test_original_mode_never_exceeds_canvas(self):
        canvas = self._canvas(500, 500, mode="original")
        canvas.set_target_dimensions(1080, 1920)
        rect, _ = canvas.fitted_rect()
        self.assertLessEqual(rect.width(), 500)
        self.assertLessEqual(rect.height(), 500)
        self.assertEqual(rect.x(), CANVAS_PADDING)

    def test_fill_mode_crops_without_moving_off_left(self):
        canvas = self._canvas(1000, 1000, mode="fill")
        canvas.set_target_dimensions(500, 1000)
        rect, _ = canvas.fitted_rect()
        self.assertEqual(rect.width(), 1000 - 2 * CANVAS_PADDING)
        self.assertGreater(rect.height(), rect.width())
        self.assertEqual(rect.x(), CANVAS_PADDING)


if __name__ == "__main__":
    unittest.main()
