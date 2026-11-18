"""Display ratio, resolution calculations, and override restoration for SUSCRCPY.

Implements aspect ratio calculations, pixel bounds validation, and safe
original display size restoration on exit.
"""
from __future__ import annotations

import logging
import math
from typing import Dict, Optional, Tuple

from core.adb_manager import AdbError, AdbManager

logger = logging.getLogger("suscrcpy.screen_manager")

# Presets mapping label to (ratio_width, ratio_height)
ASPECT_RATIOS: Dict[str, Tuple[int, int]] = {
    "1:1": (1, 1),
    "3:2": (3, 2),
    "4:3": (4, 3),
    "5:4": (5, 4),
    "16:9": (16, 9),
    "16:10": (16, 10),
    "18:9": (18, 9),
    "19:9": (19, 9),
    "19.5:9": (39, 18),
    "20:9": (20, 9),
    "21:9": (21, 9),
    "22:9": (22, 9),
    "32:9": (32, 9),
    "9:16": (9, 16),
    "9:18": (9, 18),
    "9:19.5": (18, 39),
    "9:20": (9, 20),
    "9:21": (9, 21),
}

RESOLUTION_NOTICE = (
    "Notice: Applying a resolution modifies Android's logical display settings via "
    "'wm size'. This adjusts UI layout and rendering on the actual Android device, "
    "not merely the window preview. Native resolution will be restored upon clean exit "
    "or by pressing 'Reset Resolution'."
)


class ScreenManager:
    """Manages display ratio presets, custom pixel validation, and wm size lifecycle."""

    def __init__(self, adb_manager: AdbManager) -> None:
        self.adb = adb_manager
        # Mapping from serial to original override (None if native physical)
        self._original_overrides: Dict[str, Optional[Tuple[int, int]]] = {}
        self._modified_devices: set[str] = set()

    def record_initial_resolution(self, serial: str) -> Tuple[Tuple[int, int], Optional[Tuple[int, int]]]:
        """Record the device's initial physical and override resolution before any modifications."""
        phys_res, override_res = self.adb.get_display_size(serial)
        if serial not in self._original_overrides:
            self._original_overrides[serial] = override_res
            logger.info("Recorded initial resolution for %s: physical=%s, override=%s", serial, phys_res, override_res)
        return phys_res, override_res

    def calculate_dimensions_for_ratio(
        self,
        current_w: int,
        current_h: int,
        ratio_name: str,
    ) -> Tuple[int, int]:
        """Compute new width and height while preserving current orientation and long edge."""
        if ratio_name not in ASPECT_RATIOS:
            raise ValueError(f"Unknown aspect ratio preset: '{ratio_name}'")

        rw, rh = ASPECT_RATIOS[ratio_name]
        is_portrait = current_h >= current_w

        # If preset is already specified as portrait (rw < rh), adapt accordingly
        if rw < rh:
            target_rw, target_rh = rh, rw
        else:
            target_rw, target_rh = rw, rh

        if is_portrait:
            long_edge = max(current_w, current_h)
            new_h = long_edge
            new_w = round(long_edge * target_rh / target_rw)
        else:
            long_edge = max(current_w, current_h)
            new_w = long_edge
            new_h = round(long_edge * target_rh / target_rw)

        self.validate_pixels(new_w, new_h)
        return new_w, new_h

    @staticmethod
    def calculate_aspect_ratio(width_px: int, height_px: int) -> Tuple[int, int]:
        """Calculate simplified aspect ratio using Greatest Common Divisor (GCD)."""
        if width_px <= 0 or height_px <= 0:
            return 1, 1
        gcd = math.gcd(width_px, height_px)
        return width_px // gcd, height_px // gcd

    @staticmethod
    def validate_pixels(width_val: object, height_val: object) -> Tuple[int, int]:
        """Validate integer pixel dimensions within allowed bounds [100, 10000]."""
        try:
            w = int(width_val)
            h = int(height_val)
        except (ValueError, TypeError):
            raise ValueError("Pixel width and height must be integer numbers.")

        if w < 100 or w > 10000:
            raise ValueError(f"Width {w}px is outside permitted range [100, 10000].")
        if h < 100 or h > 10000:
            raise ValueError(f"Height {h}px is outside permitted range [100, 10000].")

        return w, h

    def apply_resolution(self, serial: str, width: int, height: int) -> Tuple[int, int]:
        """Apply a custom or preset resolution to the Android device via ADB."""
        w, h = self.validate_pixels(width, height)
        # Ensure initial state is recorded before first modification
        if serial not in self._original_overrides:
            self.record_initial_resolution(serial)

        self.adb.set_display_size(serial, w, h)
        self._modified_devices.add(serial)
        logger.info("Applied resolution %dx%d to device %s", w, h, serial)
        return w, h

    def reset_resolution(self, serial: str) -> Tuple[int, int]:
        """Reset the display resolution override back to native physical size."""
        self.adb.reset_display_size(serial)
        self._modified_devices.add(serial)
        # Reading back the physical size
        phys, _ = self.adb.get_display_size(serial)
        logger.info("Reset resolution to native physical %dx%d for %s", phys[0], phys[1], serial)
        return phys

    def restore_device(self, serial: str) -> None:
        """Restore the initial resolution that existed when the application started."""
        if serial not in self._modified_devices:
            return

        try:
            original = self._original_overrides.get(serial)
            if original is not None:
                orig_w, orig_h = original
                logger.info("Restoring original resolution %dx%d for %s", orig_w, orig_h, serial)
                self.adb.set_display_size(serial, orig_w, orig_h)
            else:
                logger.info("Restoring native physical resolution (wm size reset) for %s", serial)
                self.adb.reset_display_size(serial)
            self._modified_devices.discard(serial)
        except Exception as e:
            logger.error("Failed to restore initial resolution for %s: %s", serial, e)

    def restore_all(self) -> None:
        """Restore all modified devices on application shutdown."""
        for serial in list(self._modified_devices):
            self.restore_device(serial)
