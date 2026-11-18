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
# Supports all 19 standardized aspect ratio presets (both portrait and landscape equivalents)
ASPECT_RATIOS: Dict[str, Tuple[int, int]] = {
    # 1:1 Neutral Square
    "1:1": (1, 1),
    # Common Standards
    "3:2": (3, 2),
    "4:3": (4, 3),
    "5:4": (5, 4),
    "16:10": (16, 10),
    # Portrait equivalents (Standard & Modern smartphones)
    "9:16": (9, 16),
    "9:18": (9, 18),
    "9:19": (9, 19),
    "9:19.5": (18, 39),
    "9:20": (9, 20),
    "9:21": (9, 21),
    "9:22": (9, 22),
    # Landscape equivalents (Monitors, handhelds, widescreen & ultrawide)
    "16:9": (16, 9),
    "18:9": (18, 9),
    "19:9": (19, 9),
    "19.5:9": (39, 18),
    "20:9": (20, 9),
    "21:9": (21, 9),
    "22:9": (22, 9),
    "32:9": (32, 9),
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
        """Compute new width and height while strictly preserving device orientation (portrait vs landscape)."""
        if ratio_name not in ASPECT_RATIOS:
            raise ValueError(f"Unknown aspect ratio preset: '{ratio_name}'")

        r1, r2 = ASPECT_RATIOS[ratio_name]
        is_portrait = current_h >= current_w

        major = max(r1, r2)
        minor = min(r1, r2)

        if is_portrait:
            # Portrait: Height is the long edge (major factor), Width is the short edge (minor factor)
            long_edge = max(current_w, current_h)
            new_h = long_edge
            new_w = round(long_edge * minor / major)
        else:
            # Landscape: Width is the long edge (major factor), Height is the short edge (minor factor)
            long_edge = max(current_w, current_h)
            new_w = long_edge
            new_h = round(long_edge * minor / major)

        self.validate_pixels(new_w, new_h)
        return new_w, new_h

    @staticmethod
    def calculate_aspect_ratio(width_px: int, height_px: int) -> Tuple[int, int]:
        """Calculate simplified aspect ratio using Greatest Common Divisor (GCD)."""
        if width_px <= 0 or height_px <= 0:
            return 1, 1
        gcd = math.gcd(width_px, height_px)
        return width_px // gcd, height_px // gcd

    def validate_pixels(self, width: int, height: int) -> Tuple[int, int]:
        """Ensure pixel dimensions are positive integers within the safe [100, 10000] range."""
        if not (isinstance(width, int) and isinstance(height, int)):
            raise ValueError(f"Pixel dimensions must be integers. Received ({type(width)}, {type(height)}).")

        if not (100 <= width <= 10000 and 100 <= height <= 10000):
            raise ValueError(
                f"Resolution {width}x{height} outside supported safety limits [100 - 10000 px]. "
                "Values below 100 or above 10000 may cause Android SurfaceFlinger crashes."
            )
        return width, height

    def apply_resolution(self, serial: str, width: int, height: int, verify: bool = True) -> Tuple[int, int]:
        """Apply a resolution override via ADB 'wm size' and verify actual application on device.

        Returns verified (override_w, override_h) tuple.
        """
        self.validate_pixels(width, height)
        # Ensure we recorded initial state before first modification
        if serial not in self._original_overrides:
            self.record_initial_resolution(serial)

        logger.info("Applying resolution override %dx%d on %s", width, height, serial)
        self.adb.set_display_size(serial, width, height)
        self._modified_devices.add(serial)

        if verify:
            # Step 4 verification: SurfaceFlinger applies wm size asynchronously
            import time
            time.sleep(0.12)
            _, override_res = self.adb.get_display_size(serial)
            retries = 3
            while override_res != (width, height) and retries > 0:
                time.sleep(0.15)
                _, override_res = self.adb.get_display_size(serial)
                retries -= 1

            if override_res != (width, height):
                logger.warning(
                    "Resolution verification warning on %s: requested %dx%d but device reports override=%s",
                    serial, width, height, override_res
                )
            return override_res or (width, height)
        return width, height

    def reset_resolution(self, serial: str) -> Tuple[int, int]:
        """Reset the display resolution override on the device."""
        import time
        logger.info("Resetting resolution on device %s", serial)
        self.adb.reset_display_size(serial)
        self._modified_devices.discard(serial)
        time.sleep(0.12)
        phys_res, _ = self.adb.get_display_size(serial)
        return phys_res

    def restore_device(self, serial: str) -> None:
        """Restore initial resolution on the specified device."""
        self.reset_resolution(serial)

    def restore_all(self) -> None:
        """Clean-up handler: safely restores initial state on all modified devices upon application exit."""
        for serial in list(self._modified_devices):
            try:
                orig_override = self._original_overrides.get(serial)
                if orig_override is not None:
                    ow, oh = orig_override
                    logger.info("Restoring original override %dx%d on %s", ow, oh, serial)
                    self.adb.set_display_size(serial, ow, oh)
                else:
                    logger.info("Restoring native physical size on %s", serial)
                    self.adb.reset_display_size(serial)
            except Exception as e:
                logger.error("Failed to restore display size for %s: %s", serial, e)
        self._modified_devices.clear()
