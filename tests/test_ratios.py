"""Unit tests for aspect ratio math and pixel dimension validation."""
import unittest

from core.screen_manager import ASPECT_RATIOS, ScreenManager


class DummyAdb:
    def __init__(self):
        self.calls = []

    def get_display_size(self, serial):
        return (1080, 2400), None

    def set_display_size(self, serial, w, h):
        self.calls.append(("set", serial, w, h))

    def reset_display_size(self, serial):
        self.calls.append(("reset", serial))


class TestRatioCalculations(unittest.TestCase):
    def setUp(self):
        self.adb = DummyAdb()
        self.sm = ScreenManager(self.adb)

    def test_portrait_ratios(self):
        # Initial 1080x1920 (portrait, height=1920 is long edge)
        # 16:9 ratio in portrait -> 1920 * 9 / 16 = 1080
        w, h = self.sm.calculate_dimensions_for_ratio(1080, 1920, "16:9")
        self.assertEqual(h, 1920)
        self.assertEqual(w, 1080)

        # 4:3 ratio in portrait -> 1920 * 3 / 4 = 1440
        w, h = self.sm.calculate_dimensions_for_ratio(1080, 1920, "4:3")
        self.assertEqual(h, 1920)
        self.assertEqual(w, 1440)

        # 1:1 ratio -> square -> 1920x1920
        w, h = self.sm.calculate_dimensions_for_ratio(1080, 1920, "1:1")
        self.assertEqual(h, 1920)
        self.assertEqual(w, 1920)

    def test_landscape_ratios(self):
        # Initial 1920x1080 (landscape, width=1920 is long edge)
        # 16:9 ratio in landscape -> width=1920, height = 1920 * 9 / 16 = 1080
        w, h = self.sm.calculate_dimensions_for_ratio(1920, 1080, "16:9")
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)

        # 4:3 ratio in landscape -> width=1920, height = 1920 * 3 / 4 = 1440
        w, h = self.sm.calculate_dimensions_for_ratio(1920, 1080, "4:3")
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1440)

    def test_pixel_bounds_validation(self):
        # Valid pixels
        w, h = self.sm.validate_pixels(720, 1280)
        self.assertEqual((w, h), (720, 1280))

        # Out of bounds
        with self.assertRaises(ValueError):
            self.sm.validate_pixels(50, 1000)

        with self.assertRaises(ValueError):
            self.sm.validate_pixels(1080, 20000)

        with self.assertRaises(ValueError):
            self.sm.validate_pixels("invalid", 1000)

    def test_resolution_restoration_lifecycle(self):
        serial = "TEST_DEVICE_01"
        self.sm.record_initial_resolution(serial)
        self.sm.apply_resolution(serial, 720, 1280)
        self.assertIn(("set", serial, 720, 1280), self.adb.calls)

        # Restore
        self.sm.restore_device(serial)
        self.assertIn(("reset", serial), self.adb.calls)


if __name__ == "__main__":
    unittest.main()
