"""Display resolution and aspect-ratio control for SUSCRCPY.

Applies logical resolution overrides through ``adb shell wm size``, verifies that
Android actually accepted the requested size, and guarantees that every override
is restored to the device's original state on exit.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Dict, Optional, Tuple

from core.adb_manager import AdbError, AdbManager

logger = logging.getLogger("suscrcpy.screen_manager")

# Canonical presets. Each entry is a *shape*: the long-edge factor comes first.
ASPECT_RATIOS: Dict[str, Tuple[int, int]] = {
    "1:1": (1, 1),
    "3:2": (3, 2),
    "4:3": (4, 3),
    "5:4": (5, 4),
    "16:10": (16, 10),
    "16:9": (16, 9),
    "18:9": (18, 9),
    "19:9": (19, 9),
    "19.5:9": (39, 18),
    "20:9": (20, 9),
    "21:9": (21, 9),
    "22:9": (22, 9),
    "32:9": (32, 9),
    "9:16": (16, 9),
    "9:18": (18, 9),
    "9:19": (19, 9),
    "9:19.5": (39, 18),
    "9:20": (20, 9),
    "9:21": (21, 9),
    "9:22": (22, 9),
}

# Preset order used by the UI (portrait shapes first, then landscape/desktop shapes).
PRESET_ORDER = [
    "9:16", "9:18", "9:19", "9:19.5", "9:20", "9:21", "9:22",
    "1:1", "3:2", "4:3", "5:4", "16:9", "16:10",
    "18:9", "19:9", "19.5:9", "20:9", "21:9", "22:9", "32:9",
]

RESOLUTION_NOTICE = (
    "Applying a resolution changes the device's logical display through 'wm size'. "
    "The native size is restored automatically on exit or with Reset."
)

# Preferred label for a fully reduced (long, short) shape: portrait, landscape.
_SHAPE_LABELS = {
    (1, 1): ("1:1", "1:1"),
    (3, 2): ("2:3", "3:2"),
    (4, 3): ("3:4", "4:3"),
    (5, 4): ("4:5", "5:4"),
    (8, 5): ("5:8", "16:10"),
    (16, 9): ("9:16", "16:9"),
    (2, 1): ("9:18", "18:9"),
    (19, 9): ("9:19", "19:9"),
    (13, 6): ("9:19.5", "19.5:9"),
    (20, 9): ("9:20", "20:9"),
    (21, 9): ("9:21", "21:9"),
    (22, 9): ("9:22", "22:9"),
    (32, 9): ("9:32", "32:9"),
}


class ScreenManager:
    """Owns display ratio math and the ``wm size`` override lifecycle."""

    def __init__(self, adb_manager: AdbManager) -> None:
        self.adb = adb_manager
        self._original_overrides: Dict[str, Optional[Tuple[int, int]]] = {}
        self._modified_devices: set[str] = set()

    # ------------------------------------------------------------------ state
    def record_initial_resolution(
        self, serial: str
    ) -> Tuple[Tuple[int, int], Optional[Tuple[int, int]]]:
        """Remember the device's physical size and pre-existing override once."""
        phys_res, override_res = self.adb.get_display_size(serial)
        if serial not in self._original_overrides:
            self._original_overrides[serial] = override_res
            logger.info(
                "Recorded initial resolution for %s: physical=%s override=%s",
                serial, phys_res, override_res,
            )
        return phys_res, override_res

    def get_active_size(self, serial: str) -> Tuple[Tuple[int, int], Optional[Tuple[int, int]]]:
        """Return (physical, override) exactly as reported by the device."""
        return self.adb.get_display_size(serial)

    # ---------------------------------------------------------------- ratios
    @staticmethod
    def calculate_aspect_ratio(width_px: int, height_px: int) -> Tuple[int, int]:
        """Reduce pixel dimensions to the smallest exact integer ratio."""
        if width_px <= 0 or height_px <= 0:
            return 1, 1
        divisor = math.gcd(width_px, height_px)
        return width_px // divisor, height_px // divisor

    @staticmethod
    def ratio_label(width_px: int, height_px: int) -> str:
        """Exact ratio label using preset notation where one applies (e.g. ``9:16``)."""
        rw, rh = ScreenManager.calculate_aspect_ratio(width_px, height_px)
        portrait = height_px >= width_px
        long_side, short_side = max(rw, rh), min(rw, rh)
        divisor = math.gcd(long_side, short_side)
        labels = _SHAPE_LABELS.get((long_side // divisor, short_side // divisor))
        if labels:
            return labels[0] if portrait else labels[1]
        return f"{rw}:{rh}"

    def calculate_dimensions_for_ratio(
        self,
        current_w: int,
        current_h: int,
        ratio_name: str,
    ) -> Tuple[int, int]:
        """Return pixel dimensions matching ``ratio_name`` in the current orientation.

        The long edge of the current display is preserved so the device keeps its
        native scale; only the short edge is recalculated.
        """
        if ratio_name not in ASPECT_RATIOS:
            raise ValueError(f"Unknown aspect ratio preset: '{ratio_name}'")

        long_factor, short_factor = ASPECT_RATIOS[ratio_name]
        long_edge = max(current_w, current_h)

        # Snap to an integer multiple of the ratio so the resulting size reduces to
        # exactly the requested ratio instead of being off by a rounding pixel.
        multiple = max(1, long_edge // long_factor)
        long_px = multiple * long_factor
        short_px = multiple * short_factor

        if current_h >= current_w:  # portrait
            new_w, new_h = short_px, long_px
        else:                        # landscape
            new_w, new_h = long_px, short_px

        return self.validate_pixels(new_w, new_h)

    @staticmethod
    def validate_pixels(width: int, height: int) -> Tuple[int, int]:
        """Reject sizes that SurfaceFlinger cannot represent safely."""
        if not (isinstance(width, int) and isinstance(height, int)):
            raise ValueError("Pixel dimensions must be integers.")
        if not (100 <= width <= 10000 and 100 <= height <= 10000):
            raise ValueError(
                f"Resolution {width}x{height} is outside the supported range "
                "[100 - 10000 px]."
            )
        return width, height

    # ---------------------------------------------------------------- apply
    def apply_resolution(
        self, serial: str, width: int, height: int, verify: bool = True
    ) -> Tuple[int, int]:
        """Apply ``width x height`` via ``wm size`` and return what the device reports."""
        self.validate_pixels(width, height)
        if serial not in self._original_overrides:
            self.record_initial_resolution(serial)

        logger.info("Applying resolution override %dx%d on %s", width, height, serial)
        self.adb.set_display_size(serial, width, height)
        self._modified_devices.add(serial)

        if not verify:
            return width, height

        requested = (width, height)
        _, override = self.adb.get_display_size(serial)
        for _ in range(5):
            if override == requested:
                break
            time.sleep(0.15)
            _, override = self.adb.get_display_size(serial)

        if override != requested:
            logger.warning(
                "Device %s accepted %dx%d but reports override=%s",
                serial, width, height, override,
            )
        return override or requested

    def reset_resolution(self, serial: str) -> Tuple[int, int]:
        """Clear the override and return the native physical resolution."""
        logger.info("Resetting display resolution on %s", serial)
        self.adb.reset_display_size(serial)
        self._modified_devices.discard(serial)
        phys_res, _ = self.adb.get_display_size(serial)
        return phys_res

    def restore_all(self) -> None:
        """Restore every device this session modified back to its original state."""
        for serial in list(self._modified_devices):
            try:
                original = self._original_overrides.get(serial)
                if original:
                    self.adb.set_display_size(serial, original[0], original[1])
                    logger.info("Restored original override %dx%d on %s", *original, serial)
                else:
                    self.adb.reset_display_size(serial)
                    logger.info("Restored native size on %s", serial)
            except (AdbError, Exception) as exc:  # noqa: BLE001 - never block shutdown
                logger.error("Failed to restore display size for %s: %s", serial, exc)
        self._modified_devices.clear()
