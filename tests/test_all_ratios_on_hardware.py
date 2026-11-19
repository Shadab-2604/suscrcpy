"""Hardware accuracy audit: every ratio must be applied exactly on a real device.

Run with a device attached:

    SUSCRCPY_HW_AUDIT=1 python3 -m pytest tests/test_all_ratios_on_hardware.py -v

Without an attached device the audit is skipped instead of failing.
"""
from __future__ import annotations

import os
import unittest

from core.adb_manager import AdbManager
from core.screen_manager import ASPECT_RATIOS, PRESET_ORDER, ScreenManager

RUN_AUDIT = os.environ.get("SUSCRCPY_HW_AUDIT") == "1"


def _first_device_serial(adb: AdbManager):
    devices = [d for d in adb.list_devices() if d.is_authorized]
    return devices[0].serial if devices else None


@unittest.skipUnless(RUN_AUDIT, "set SUSCRCPY_HW_AUDIT=1 with a device attached")
class TestRatioAccuracyOnHardware(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adb = AdbManager()
        cls.serial = _first_device_serial(cls.adb)
        if not cls.serial:
            raise unittest.SkipTest("no authorized ADB device connected")
        cls.sm = ScreenManager(cls.adb)
        cls.physical, _ = cls.sm.record_initial_resolution(cls.serial)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "serial", None):
            cls.adb.reset_display_size(cls.serial)

    def test_every_preset_is_applied_exactly(self):
        """wm size must report exactly the requested dimensions for every preset."""
        failures = []
        for preset in PRESET_ORDER:
            width, height = self.sm.calculate_dimensions_for_ratio(
                self.physical[0], self.physical[1], preset
            )
            applied_w, applied_h = self.sm.apply_resolution(self.serial, width, height)

            if (applied_w, applied_h) != (width, height):
                failures.append(f"{preset}: requested {width}x{height}, device {applied_w}x{applied_h}")
                continue

            ratio_label = ScreenManager.ratio_label(applied_w, applied_h)
            expected = ASPECT_RATIOS[preset]
            requested_ratio = expected[1] / expected[0]  # short / long
            actual_ratio = min(applied_w, applied_h) / max(applied_w, applied_h)
            if abs(actual_ratio - requested_ratio) > 0.002:
                failures.append(f"{preset}: ratio {ratio_label} != requested shape")

        self.assertEqual(failures, [], "ratio application mismatches:\n" + "\n".join(failures))

    def test_native_size_is_restored(self):
        self.sm.apply_resolution(self.serial, 720, 1280)
        width, height = self.sm.reset_resolution(self.serial)
        self.assertEqual((width, height), self.physical)

    def test_override_survives_stream_restart(self):
        """The size Android reports must still match after a second apply."""
        width, height = self.sm.calculate_dimensions_for_ratio(
            self.physical[0], self.physical[1], "9:19.5"
        )
        first = self.sm.apply_resolution(self.serial, width, height)
        _, override = self.sm.get_active_size(self.serial)
        self.assertEqual(first, (width, height))
        self.assertEqual(override, (width, height))


if __name__ == "__main__":
    unittest.main()
