"""Screenshot Capture & Annotation Manager for SUSCRCPY.

Captures Android device displays directly through ADB/scrcpy framebuffers,
manages raw image storage, and provides non-destructive image annotations
(rectangles, arrows, text, blur sensitive data).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen

from core.adb_manager import AdbManager

logger = logging.getLogger("suscrcpy.screenshot_manager")


@dataclass
class ScreenshotMetadata:
    """Metadata for a captured device screenshot."""
    id: str
    raw_path: str
    annotated_path: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    device_serial: Optional[str] = None
    package_name: Optional[str] = None
    session_id: Optional[str] = None
    width: int = 0
    height: int = 0
    file_size_bytes: int = 0
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ScreenshotManager(QObject):
    """Manages capturing, saving, and annotating Android device screenshots."""

    screenshot_captured = Signal(object)  # ScreenshotMetadata
    screenshot_annotated = Signal(object) # ScreenshotMetadata
    capture_failed = Signal(str)          # error message

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
        session_id: Optional[str] = None,
        package_name: Optional[str] = None,
    ) -> Optional[ScreenshotMetadata]:
        """Capture the current Android screen using ADB screencap."""
        destination_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp_str}.png"
        raw_filepath = destination_dir / filename

        png_bytes = b""
        # Method 1: exec-out screencap -p (fastest on Linux)
        try:
            cmd = [self.adb.adb_path, "-s", serial, "exec-out", "screencap", "-p"]
            import subprocess
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if res.returncode == 0 and len(res.stdout) > 100 and res.stdout.startswith(b"\x89PNG"):
                png_bytes = res.stdout
        except Exception as e:
            logger.debug("exec-out screencap failed on %s: %s", serial, e)

        # Method 2: Fallback to /sdcard/ temp file and pull
        if not png_bytes:
            try:
                temp_device_path = f"/sdcard/suscrcpy_{timestamp_str}.png"
                self.adb.run(["shell", "screencap", "-p", temp_device_path], serial=serial)
                self.adb.run(["pull", temp_device_path, str(raw_filepath)], serial=serial)
                self.adb.run(["shell", "rm", "-f", temp_device_path], serial=serial)
                if raw_filepath.exists():
                    with open(raw_filepath, "rb") as f:
                        png_bytes = f.read()
            except Exception as e:
                err_msg = f"Failed to capture screenshot from {serial}: {e}"
                logger.error(err_msg)
                self.capture_failed.emit(err_msg)
                return None

        if not png_bytes:
            err_msg = f"No valid PNG image data received from {serial}"
            logger.error(err_msg)
            self.capture_failed.emit(err_msg)
            return None

        # Write file if not already pulled
        if not raw_filepath.exists():
            with open(raw_filepath, "wb") as f:
                f.write(png_bytes)

        # Inspect dimensions and hash
        qimg = QImage()
        qimg.loadFromData(png_bytes)
        width = qimg.width() if not qimg.isNull() else 0
        height = qimg.height() if not qimg.isNull() else 0

        sha256 = hashlib.sha256(png_bytes).hexdigest()
        shot_id = f"SHOT-{timestamp_str}"

        meta = ScreenshotMetadata(
            id=shot_id,
            raw_path=str(raw_filepath),
            timestamp=datetime.now().isoformat(),
            device_serial=serial,
            package_name=package_name,
            session_id=session_id,
            width=width,
            height=height,
            file_size_bytes=len(png_bytes),
            sha256=sha256,
        )
        self._history.append(meta)
        logger.info("Captured screenshot: %s (%dx%d, %d bytes)", raw_filepath.name, width, height, len(png_bytes))
        self.screenshot_captured.emit(meta)
        return meta

    def annotate_screenshot(
        self,
        meta: ScreenshotMetadata,
        rectangles: Optional[List[Tuple[QRect, QColor, int]]] = None,
        arrows: Optional[List[Tuple[QPoint, QPoint, QColor, int]]] = None,
        texts: Optional[List[Tuple[QPoint, str, QColor, int]]] = None,
        blur_regions: Optional[List[QRect]] = None,
    ) -> Optional[Path]:
        """Apply non-destructive visual annotations and save as a separate _annotated.png copy."""
        raw_path = Path(meta.raw_path)
        if not raw_path.exists():
            return None

        image = QImage(str(raw_path))
        if image.isNull():
            return None

        # 1. Apply Blurs/Redactions
        if blur_regions:
            for region in blur_regions:
                intersected = region.intersected(image.rect())
                if not intersected.isEmpty():
                    self._pixelate_region(image, intersected)

        # 2. Draw Vector Annotations
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        # Rectangles
        if rectangles:
            for rect, color, pen_width in rectangles:
                pen = QPen(color, pen_width, Qt.SolidLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect)

        # Arrows
        if arrows:
            for start, end, color, pen_width in arrows:
                self._draw_arrow(painter, start, end, color, pen_width)

        # Text labels
        if texts:
            for pos, text, color, font_size in texts:
                font = QFont("Sans-Serif", font_size, QFont.Bold)
                painter.setFont(font)
                painter.setPen(color)
                painter.drawText(pos, text)

        painter.end()

        # Save annotated copy
        stem = raw_path.stem
        annotated_path = raw_path.parent / f"{stem}_annotated.png"
        image.save(str(annotated_path), "PNG")

        meta.annotated_path = str(annotated_path)
        logger.info("Saved annotated screenshot to %s", annotated_path.name)
        self.screenshot_annotated.emit(meta)
        return annotated_path

    @staticmethod
    def _pixelate_region(image: QImage, rect: QRect, block_size: int = 12) -> None:
        """Pixelate a sensitive region for privacy/redaction."""
        for y in range(rect.top(), rect.bottom(), block_size):
            for x in range(rect.left(), rect.right(), block_size):
                bw = min(block_size, rect.right() - x + 1)
                bh = min(block_size, rect.bottom() - y + 1)
                # Compute average color in block
                total_r = total_g = total_b = 0
                count = 0
                for py in range(y, y + bh):
                    for px in range(x, x + bw):
                        c = QColor.fromRgb(image.pixel(px, py))
                        total_r += c.red()
                        total_g += c.green()
                        total_b += c.blue()
                        count += 1
                if count > 0:
                    avg_color = QColor(total_r // count, total_g // count, total_b // count)
                    for py in range(y, y + bh):
                        for px in range(x, x + bw):
                            image.setPixelColor(px, py, avg_color)

    @staticmethod
    def _draw_arrow(painter: QPainter, start: QPoint, end: QPoint, color: QColor, width: int) -> None:
        """Render directional vector arrow from start to end."""
        import math
        painter.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = max(14, width * 3)
        p1 = QPoint(
            int(end.x() - arrow_size * math.cos(angle - math.pi / 6)),
            int(end.y() - arrow_size * math.sin(angle - math.pi / 6)),
        )
        p2 = QPoint(
            int(end.x() - arrow_size * math.cos(angle + math.pi / 6)),
            int(end.y() - arrow_size * math.sin(angle + math.pi / 6)),
        )
        painter.setBrush(QBrush(color))
        painter.drawPolygon([end, p1, p2])
