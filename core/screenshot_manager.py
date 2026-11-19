"""Screenshot capture for SUSCRCPY.

Grabs the live device framebuffer through ADB, writes a PNG to a folder, and
reports its real pixel dimensions so what is saved can be verified.
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from core.adb_manager import AdbManager

logger = logging.getLogger("suscrcpy.screenshot_manager")


@dataclass
class ScreenshotMetadata:
    """Metadata describing a captured screenshot."""

    id: str
    raw_path: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    device_serial: Optional[str] = None
    width: int = 0
    height: int = 0
    file_size_bytes: int = 0
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ScreenshotManager(QObject):
    """Captures PNG screenshots from a connected device."""

    screenshot_captured = Signal(object)  # ScreenshotMetadata
    capture_failed = Signal(str)

    def __init__(self, adb_manager: AdbManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.adb = adb_manager
        self._history: List[ScreenshotMetadata] = []

    @property
    def history(self) -> List[ScreenshotMetadata]:
        return list(self._history)

    def capture_screenshot(
        self,
        serial: str,
        destination_dir: Path,
    ) -> Optional[ScreenshotMetadata]:
        """Capture the current screen; return metadata or emit ``capture_failed``."""
        destination_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = destination_dir / f"screenshot_{stamp}.png"

        data = self._read_png(serial, stamp)

        if data:
            path.write_bytes(data)
        elif path.exists():
            data = path.read_bytes()

        if not data or not data.startswith(b"\x89PNG"):
            message = f"Could not read a PNG screenshot from {serial}"
            logger.error(message)
            self.capture_failed.emit(message)
            return None

        image = QImage()
        image.loadFromData(data)
        meta = ScreenshotMetadata(
            id=f"SHOT-{stamp}",
            raw_path=str(path),
            device_serial=serial,
            width=image.width() if not image.isNull() else 0,
            height=image.height() if not image.isNull() else 0,
            file_size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
        self._history.append(meta)
        logger.info("Screenshot saved: %s (%dx%d)", path.name, meta.width, meta.height)
        self.screenshot_captured.emit(meta)
        return meta

    def _read_png(self, serial: str, stamp: str) -> bytes:
        """Try the fast exec-out path, then fall back to pull."""
        try:
            result = subprocess.run(
                [self.adb.adb_path, "-s", serial, "exec-out", "screencap", "-p"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.startswith(b"\x89PNG"):
                return result.stdout
        except Exception as exc:  # noqa: BLE001 - fall back to pull
            logger.debug("exec-out screencap failed: %s", exc)

        remote = f"/sdcard/suscrcpy_{stamp}.png"
        temp = Path.home() / f".suscrcpy_{stamp}.png"
        try:
            self.adb.run(["shell", "screencap", "-p", remote], serial=serial)
            self.adb.run(["pull", remote, str(temp)], serial=serial)
            self.adb.run(["shell", "rm", "-f", remote], serial=serial)
            if temp.exists():
                return temp.read_bytes()
        except Exception as exc:  # noqa: BLE001
            logger.debug("screencap pull fallback failed: %s", exc)
        finally:
            temp.unlink(missing_ok=True)
        return b""
