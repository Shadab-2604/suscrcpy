"""Unit tests for Screen Synchronization, ViewportCanvas geometry fitting, and aspect ratio presets."""
import unittest
from PySide6 import QtCore

from core.screen_manager import ASPECT_RATIOS, ScreenManager
from ui.screen_view import ViewportCanvas


class DummyAdb:
    def __init__(self):
        self.calls = []
        self.override = None

    def get_display_size(self, serial):
        return (1080, 2400), self.override

    def set_display_size(self, serial, w, h):
        self.calls.append(("set", serial, w, h))
        self.override = (w, h)

    def reset_display_size(self, serial):
        self.calls.append(("reset", serial))
        self.override = None


class TestScreenSynchronization(unittest.TestCase):
    def setUp(self):
        self.adb = DummyAdb()
        self.sm = ScreenManager(self.adb)

    def test_all_19_presets_present(self):
        required_presets = [
            "1:1", "3:2", "4:3", "5:4",
            "9:16", "9:18", "9:19", "9:19.5", "9:20", "9:21", "9:22",
            "16:9", "16:10", "18:9", "19:9", "19.5:9", "20:9", "21:9", "32:9"
        ]
        for preset in required_presets:
            self.assertIn(preset, ASPECT_RATIOS, f"Missing required aspect ratio preset: {preset}")

    def test_step4_verification_applied_successfully(self):
        serial = "DEVICE_XYZ"
        w, h = self.sm.apply_resolution(serial, 800, 1280, verify=True)
        self.assertEqual((w, h), (800, 1280))
        self.assertEqual(self.adb.override, (800, 1280))

    def test_fitted_geometry_pillarboxing(self):
        """When canvas is wider than 9:16 stream, canvas should pillarbox (black bars on left/right)."""
        canvas = ViewportCanvas()
        canvas.set_display_mode("fit")

        # Available canvas: 1200w x 800h. Stream: 720w x 1280h (portrait 9:16 = 0.5625)
        rect = canvas.calculate_fitted_geometry(avail_w=1200, avail_h=800, target_w=720, target_h=1280)

        self.assertEqual(rect.height(), 800)
        expected_w = int(round(800 * (720 / 1280)))  # 450
        self.assertEqual(rect.width(), expected_w)
        self.assertTrue(rect.x() > 0, "Pillarboxing should center container with horizontal offset")
        self.assertEqual(rect.x(), (1200 - expected_w) // 2)
        self.assertEqual(rect.y(), 0)

    def test_fitted_geometry_letterboxing(self):
        """When canvas is taller than 16:9 stream, canvas should letterbox (black bars on top/bottom)."""
        canvas = ViewportCanvas()
        canvas.set_display_mode("fit")

        # Available canvas: 800w x 1200h. Stream: 1920w x 1080h (landscape 16:9 = 1.777)
        rect = canvas.calculate_fitted_geometry(avail_w=800, avail_h=1200, target_w=1920, target_h=1080)

        self.assertEqual(rect.width(), 800)
        expected_h = int(round(800 / (1920 / 1080)))  # 450
        self.assertEqual(rect.height(), expected_h)
        self.assertTrue(rect.y() > 0, "Letterboxing should center container with vertical offset")
        self.assertEqual(rect.y(), (1200 - expected_h) // 2)
        self.assertEqual(rect.x(), 0)

    def test_fitted_geometry_square_ratio(self):
        """1:1 square ratio fitting on rectangular canvas."""
        canvas = ViewportCanvas()
        canvas.set_display_mode("fit")

        # Available canvas: 800w x 600h. Stream: 1080w x 1080h
        rect = canvas.calculate_fitted_geometry(avail_w=800, avail_h=600, target_w=1080, target_h=1080)
        self.assertEqual(rect.width(), 600)
        self.assertEqual(rect.height(), 600)
        self.assertEqual(rect.x(), 100)
        self.assertEqual(rect.y(), 0)

    def test_fitted_geometry_original_1to1_mode(self):
        """Original size mode preserves exact stream pixels."""
        canvas = ViewportCanvas()
        canvas.set_display_mode("original")

        rect = canvas.calculate_fitted_geometry(avail_w=1000, avail_h=1000, target_w=400, target_h=800)
        self.assertEqual(rect.width(), 400)
        self.assertEqual(rect.height(), 800)
        self.assertEqual(rect.x(), 300)
        self.assertEqual(rect.y(), 100)

    def test_fitted_geometry_fill_mode(self):
        """Fill mode scales to occupy complete container with cropping."""
        canvas = ViewportCanvas()
        canvas.set_display_mode("fill")

        # Available canvas: 1000w x 1000h. Stream: 500w x 1000h (aspect 0.5)
        rect = canvas.calculate_fitted_geometry(avail_w=1000, avail_h=1000, target_w=500, target_h=1000)
        # scale = max(1000/500, 1000/1000) = 2.0 -> rendered_w = 1000, rendered_h = 2000
        self.assertEqual(rect.width(), 1000)
        self.assertEqual(rect.height(), 2000)
        self.assertEqual(rect.x(), 0)
        self.assertEqual(rect.y(), -500)  # Cropped vertically by parent

    def test_fitted_geometry_ultrawide_32_9(self):
        """Super Ultrawide 32:9 fitting on typical 680x768 left panel."""
        canvas = ViewportCanvas()
        canvas.set_display_mode("fit")

        # Stream: 3840 x 1080 (32:9). Left panel: 680w x 768h
        rect = canvas.calculate_fitted_geometry(avail_w=680, avail_h=768, target_w=3840, target_h=1080)
        self.assertTrue(rect.width() <= 680, "Width must fit within left panel")
        self.assertTrue(rect.height() <= 768, "Height must fit within left panel")
        self.assertTrue(rect.x() >= 0, "No horizontal overflow")
        self.assertTrue(rect.y() >= 0, "No vertical overflow")

    def test_all_19_presets_fit_within_left_panel(self):
        """Every single preset must strictly fit within left panel bounds with zero distortion."""
        canvas = ViewportCanvas()
        canvas.set_display_mode("fit")
        avail_w, avail_h = 680, 768

        for preset_name, (rw, rh) in ASPECT_RATIOS.items():
            # Test portrait orientation
            rect_p = canvas.calculate_fitted_geometry(avail_w, avail_h, target_w=min(rw, rh) * 100, target_h=max(rw, rh) * 100)
            self.assertTrue(rect_p.width() <= avail_w, f"Preset {preset_name} portrait width exceeded panel: {rect_p.width()} > {avail_w}")
            self.assertTrue(rect_p.height() <= avail_h, f"Preset {preset_name} portrait height exceeded panel: {rect_p.height()} > {avail_h}")
            self.assertTrue(rect_p.x() >= 0 and rect_p.y() >= 0, f"Preset {preset_name} portrait offset invalid: {rect_p}")

            # Test landscape orientation
            rect_l = canvas.calculate_fitted_geometry(avail_w, avail_h, target_w=max(rw, rh) * 100, target_h=min(rw, rh) * 100)
            self.assertTrue(rect_l.width() <= avail_w, f"Preset {preset_name} landscape width exceeded panel: {rect_l.width()} > {avail_w}")
            self.assertTrue(rect_l.height() <= avail_h, f"Preset {preset_name} landscape height exceeded panel: {rect_l.height()} > {avail_h}")
            self.assertTrue(rect_l.x() >= 0 and rect_l.y() >= 0, f"Preset {preset_name} landscape offset invalid: {rect_l}")


if __name__ == "__main__":
    unittest.main()
