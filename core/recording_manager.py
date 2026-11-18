"""Screen Recording Manager for SUSCRCPY.

Records the connected Android device display in real-time to MP4 using native
Android screenrecord, manages duration and file size tracking, safe signal
finalization (to prevent corrupt MP4 moov atoms), and device disconnect recovery.
"""
from __future__ import annotations

import hashlib
import logging
import os
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from core.adb_manager import AdbManager

logger = logging.getLogger("suscrcpy.recording_manager")


@dataclass
class RecordingMetadata:
    """Metadata for a captured screen recording."""
    id: str
    filepath: str
    duration_seconds: int = 0
    file_size_bytes: int = 0
    sha256: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    device_serial: Optional[str] = None
    package_name: Optional[str] = None
    session_id: Optional[str] = None
    is_partial: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RecordingManager(QObject):
    """Coordinates starting, duration tracking, stopping and exporting device video recordings."""

    recording_started = Signal(str)           # remote_path
    recording_tick = Signal(int)              # elapsed seconds
    recording_completed = Signal(object)      # RecordingMetadata
    recording_failed = Signal(str)            # error message

    def __init__(self, adb_manager: AdbManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.adb = adb_manager
        self._process: Optional[subprocess.Popen] = None
        self._start_time: float = 0
        self._serial: Optional[str] = None
        self._remote_path: Optional[str] = None
        self._local_filepath: Optional[Path] = None
        self._session_id: Optional[str] = None
        self._package_name: Optional[str] = None
        self._rec_id: Optional[str] = None

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._on_tick)

    @property
    def is_recording(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def elapsed_seconds(self) -> int:
        if not self._start_time:
            return 0
        return int(time.time() - self._start_time)

    def start_recording(
        self,
        serial: str,
        destination_dir: Path,
        session_id: Optional[str] = None,
        package_name: Optional[str] = None,
        bit_rate_bps: int = 4000000,
        time_limit_sec: int = 180,
    ) -> bool:
        """Start real-time device screen recording."""
        if self.is_recording:
            logger.warning("Screen recording is already in progress")
            return False

        destination_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._rec_id = f"REC-{timestamp_str}"
        self._serial = serial
        self._session_id = session_id
        self._package_name = package_name
        self._remote_path = f"/sdcard/suscrcpy_rec_{timestamp_str}.mp4"
        self._local_filepath = destination_dir / f"recording_{timestamp_str}.mp4"

        cmd = [
            self.adb.adb_path,
            "-s", serial,
            "shell",
            "screenrecord",
            f"--bit-rate={bit_rate_bps}",
            f"--time-limit={time_limit_sec}",
            self._remote_path,
        ]

        try:
            logger.info("Spawning screenrecord process on %s: %s", serial, " ".join(cmd))
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
            self._start_time = time.time()
            self._ticker.start()
            self.recording_started.emit(self._remote_path)
            return True
        except Exception as e:
            err_msg = f"Failed to start screen recording on {serial}: {e}"
            logger.error(err_msg)
            self.recording_failed.emit(err_msg)
            self._cleanup_state()
            return False

    def _on_tick(self) -> None:
        """Emit elapsed time and check if device process died unexpectedly."""
        elapsed = self.elapsed_seconds
        self.recording_tick.emit(elapsed)
        if self._process and self._process.poll() is not None:
            # Process terminated naturally (e.g. hit time-limit)
            logger.info("screenrecord process exited automatically")
            self.stop_recording(is_natural_exit=True)

    def stop_recording(self, is_natural_exit: bool = False) -> Optional[RecordingMetadata]:
        """Gracefully stop screen recording, pull MP4 to host, and compute integrity hash."""
        if not self._process and not self._local_filepath:
            return None

        self._ticker.stop()
        duration = self.elapsed_seconds
        serial = self._serial
        remote = self._remote_path
        local = self._local_filepath
        proc = self._process

        is_partial = False

        if proc and proc.poll() is None and not is_natural_exit:
            logger.info("Sending SIGINT to screenrecord to finalize MP4 file...")
            try:
                # Tell adb to interrupt so screenrecord writes moov atom
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    proc.wait(timeout=2)
            except Exception as e:
                logger.warning("Error signaling screenrecord process: %e", e)
                is_partial = True

        # Wait a moment for Android media muxer to flush file
        time.sleep(1.0)

        # Pull recorded MP4 from device
        file_size = 0
        sha256 = ""
        if serial and remote and local:
            try:
                logger.info("Pulling recorded file from device: %s -> %s", remote, local)
                self.adb.run(["pull", remote, str(local)], serial=serial)
                self.adb.run(["shell", "rm", "-f", remote], serial=serial)
                if local.exists():
                    file_size = local.stat().st_size
                    # Calculate hash
                    hasher = hashlib.sha256()
                    with open(local, "rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            hasher.update(chunk)
                    sha256 = hasher.hexdigest()
            except Exception as e:
                logger.error("Failed to pull recording from %s: %s", serial, e)
                is_partial = True

        rec_meta = RecordingMetadata(
            id=self._rec_id or f"REC-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            filepath=str(local) if local else "",
            duration_seconds=duration,
            file_size_bytes=file_size,
            sha256=sha256,
            timestamp=datetime.now().isoformat(),
            device_serial=serial,
            package_name=self._package_name,
            session_id=self._session_id,
            is_partial=is_partial,
        )

        self._cleanup_state()
        logger.info("Screen recording completed: %s (%ds, %d bytes)", local.name if local else "", duration, file_size)
        self.recording_completed.emit(rec_meta)
        return rec_meta

    def _cleanup_state(self) -> None:
        """Reset internal recording state."""
        self._ticker.stop()
        self._process = None
        self._start_time = 0
        self._serial = None
        self._remote_path = None
        self._local_filepath = None
        self._session_id = None
        self._package_name = None
        self._rec_id = None
