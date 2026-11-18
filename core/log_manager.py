"""High-performance Android log streaming and management for SUSCRCPY.

Supports Full Device logging and Application-specific logging with dynamic PID tracking,
crash detection, bounded GUI buffer, and streaming exports.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Set

from PySide6.QtCore import QMutex, QObject, QThread, Signal

from core.adb_manager import AdbManager
from core.error_detector import DetectionResult, ErrorDetector, LogSeverity
from core.process_manager import ProcessManager

logger = logging.getLogger("suscrcpy.log_manager")

# Standard threadtime regex:
# 11-18 10:20:30.123  1234  1245 E AndroidRuntime: FATAL EXCEPTION: main
THREADTIME_REGEX = re.compile(
    r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+([^:]*?)\s*:\s*(.*)$"
)


@dataclass
class LogEntry:
    """Represents a structured Android log line."""
    timestamp: str
    pid: int
    tid: int
    level: str  # V, D, I, W, E, F
    tag: str
    message: str
    raw: str
    detection: DetectionResult

    @property
    def is_crash(self) -> bool:
        return self.detection.is_crash

    @property
    def is_error(self) -> bool:
        return self.detection.is_error

    @property
    def is_warning(self) -> bool:
        return self.detection.is_warning


class LogStreamWorker(QThread):
    """Background worker thread that reads and processes the continuous logcat stream."""

    batch_ready = Signal(list)  # List[LogEntry]
    stats_updated = Signal(int, int, int)  # errors, warnings, crashes
    app_status_changed = Signal(str)  # Status message regarding target app
    crash_detected = Signal(object)  # LogEntry

    def __init__(
        self,
        adb_manager: AdbManager,
        serial: str,
        target_package: Optional[str] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.adb = adb_manager
        self.serial = serial
        self.target_package = target_package
        self._running = False
        self._paused = False
        self._error_detector = ErrorDetector()
        self._mutex = QMutex()
        self._proc: Optional[subprocess.Popen] = None
        self._tracked_pids: Set[int] = set()
        self._last_pid_check = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        """Pause or resume visual delivery of logs without interrupting log capture."""
        self._paused = paused

    def stop(self) -> None:
        """Stop log streaming."""
        self._running = False
        if self._proc:
            ProcessManager.instance().stop_process(self._proc, timeout=1.5)
            self._proc = None
        self.wait(2000)

    def _update_target_pids(self) -> None:
        """Poll for currently running PIDs of the target application."""
        if not self.target_package:
            return

        now = time.time()
        # Check every 2 seconds
        if now - self._last_pid_check < 2.0:
            return
        self._last_pid_check = now

        try:
            current_pids = set(self.adb.get_pids_for_package(self.serial, self.target_package))
            if current_pids != self._tracked_pids:
                if not current_pids:
                    self.app_status_changed.emit(
                        f"Application '{self.target_package}' is not running. Waiting for process..."
                    )
                else:
                    pid_str = ", ".join(str(p) for p in sorted(current_pids))
                    self.app_status_changed.emit(
                        f"Monitoring '{self.target_package}' (Active PID: {pid_str})"
                    )
                self._tracked_pids = current_pids
        except Exception as e:
            logger.debug("Error checking package PIDs: %s", e)

    def run(self) -> None:
        self._running = True
        self._error_detector.reset_counts()

        if self.target_package:
            # Initial PID discovery
            self._update_target_pids()
            if not self._tracked_pids:
                self.app_status_changed.emit(
                    f"Application '{self.target_package}' is not running. Waiting for process..."
                )

        try:
            self._proc = self.adb.spawn_logcat_stream(self.serial)
            ProcessManager.instance().register(self._proc)
        except Exception as e:
            logger.error("Failed to spawn logcat process: %s", e)
            self._running = False
            return

        batch: List[LogEntry] = []
        last_flush = time.time()

        stdout = self._proc.stdout
        if not stdout:
            self._running = False
            return

        while self._running:
            line = stdout.readline()
            if not line:
                if self._proc.poll() is not None:
                    break
                time.sleep(0.02)
                continue

            line = line.rstrip("\r\n")
            if not line:
                continue

            # Periodically verify package PIDs if in application mode
            if self.target_package:
                self._update_target_pids()

            # Parse threadtime format
            match = THREADTIME_REGEX.match(line)
            if match:
                ts, pid_s, tid_s, level_char, tag, msg = match.groups()
                pid = int(pid_s)
                tid = int(tid_s)
            else:
                # Handle continuation or unformatted messages
                ts = ""
                pid = 0
                tid = 0
                level_char = "I"
                tag = "Logcat"
                msg = line

            # Filter for specific application mode if active
            if self.target_package:
                # Only include lines matching active PIDs of the application
                if pid not in self._tracked_pids:
                    # Also permit tag matching if package name is directly in tag
                    if self.target_package.lower() not in tag.lower():
                        continue

            detection = self._error_detector.analyze(level_char, tag, msg, pid=pid)

            entry = LogEntry(
                timestamp=ts,
                pid=pid,
                tid=tid,
                level=detection.severity.value,
                tag=tag.strip(),
                message=msg,
                raw=line,
                detection=detection,
            )

            if detection.is_crash:
                self.crash_detected.emit(entry)

            if not self._paused:
                batch.append(entry)

            # Flush batch every 50ms or 50 entries to keep UI 60fps responsive
            now = time.time()
            if len(batch) >= 50 or (now - last_flush >= 0.05 and batch):
                self.batch_ready.emit(batch)
                self.stats_updated.emit(
                    self._error_detector.error_count,
                    self._error_detector.warning_count,
                    self._error_detector.crash_count,
                )
                batch = []
                last_flush = now

        # Flush any remaining entries
        if batch and not self._paused:
            self.batch_ready.emit(batch)
            self.stats_updated.emit(
                self._error_detector.error_count,
                self._error_detector.warning_count,
                self._error_detector.crash_count,
            )

        if self._proc:
            ProcessManager.instance().stop_process(self._proc, timeout=1.0)
            self._proc = None
        self._running = False


class LogManager(QObject):
    """High-level log capture coordinator managing the worker thread and full history buffer."""

    new_logs_batch = Signal(list)  # List[LogEntry]
    stats_updated = Signal(int, int, int)
    status_updated = Signal(str)
    crash_alert = Signal(object)

    def __init__(self, adb_manager: AdbManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.adb = adb_manager
        self._worker: Optional[LogStreamWorker] = None
        self._full_export_buffer: List[LogEntry] = []
        self._critical_errors_sample: List[str] = []
        self._disk_log_file: Optional[Path] = None
        self._disk_file_handle: Optional[Any] = None
        self._visible_buffer_size = 3000
        self._start_time: Optional[str] = None
        self._mode = "Full Device"
        self._target_package: Optional[str] = None
        self._serial: Optional[str] = None

    @property
    def critical_errors_sample(self) -> List[str]:
        return list(self._critical_errors_sample)

    @property
    def is_streaming(self) -> bool:
        return self._worker is not None and self._worker.is_running

    @property
    def is_paused(self) -> bool:
        return self._worker is not None and self._worker.is_paused

    @property
    def export_buffer(self) -> List[LogEntry]:
        return self._full_export_buffer

    @property
    def mode_label(self) -> str:
        return self._mode

    @property
    def start_time(self) -> Optional[str]:
        return self._start_time

    def start_capture(
        self,
        serial: str,
        target_package: Optional[str] = None,
        disk_log_path: Optional[Path] = None,
    ) -> None:
        """Start streaming logs in either Full Device mode or Target Application mode."""
        self.stop_capture()
        self._serial = serial
        self._target_package = target_package
        self._mode = f"App: {target_package}" if target_package else "Full Device"
        self._start_time = time.strftime("%Y-%m-%d %H:%M:%S")

        if disk_log_path:
            disk_log_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._disk_log_file = disk_log_path
                self._disk_file_handle = open(disk_log_path, "a", encoding="utf-8", buffering=1)
                self._disk_file_handle.write(f"\n--- LOGCAT CAPTURE STARTED: {self._start_time} [{self._mode}] ---\n")
            except Exception as e:
                logger.error("Could not open disk log file %s: %s", disk_log_path, e)
                self._disk_file_handle = None

        self._worker = LogStreamWorker(
            adb_manager=self.adb,
            serial=serial,
            target_package=target_package,
        )
        self._worker.batch_ready.connect(self._handle_batch)
        self._worker.stats_updated.connect(self.stats_updated)
        self._worker.app_status_changed.connect(self.status_updated)
        self._worker.crash_detected.connect(self.crash_alert)
        self._worker.start()

        mode_desc = f"Application '{target_package}'" if target_package else "Full Device"
        self.status_updated.emit(f"Logcat capture started [{mode_desc}]")

    def _handle_batch(self, batch: List[LogEntry]) -> None:
        self._full_export_buffer.extend(batch)
        if self._disk_file_handle:
            try:
                for entry in batch:
                    self._disk_file_handle.write(entry.raw + "\n")
                    if entry.level in ("ERROR", "CRASH"):
                        if len(self._critical_errors_sample) < 150:
                            self._critical_errors_sample.append(f"[{entry.level}] {entry.tag}: {entry.message}")
            except Exception as e:
                logger.warning("Error writing to disk log: %s", e)
        self.new_logs_batch.emit(batch)

    def pause_capture(self) -> None:
        """Pause display updates."""
        if self._worker:
            self._worker.set_paused(True)
            self.status_updated.emit("Log display paused (capture continuing in background)")

    def resume_capture(self) -> None:
        """Resume display updates."""
        if self._worker:
            self._worker.set_paused(False)
            self.status_updated.emit("Log display resumed")

    def stop_capture(self) -> None:
        """Stop the streaming logcat worker and finalize disk log file."""
        if self._worker:
            self._worker.stop()
            self._worker = None
            self.status_updated.emit("Log capture stopped")
        if self._disk_file_handle:
            try:
                self._disk_file_handle.write(f"--- LOGCAT CAPTURE STOPPED: {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                self._disk_file_handle.flush()
                self._disk_file_handle.close()
            except Exception as e:
                logger.debug("Error closing disk log file: %s", e)
            self._disk_file_handle = None

    def clear_view(self) -> None:
        """Clear local in-memory view buffer without modifying device buffer."""
        # Note: Do not clear _full_export_buffer so users can still download complete logs
        self.status_updated.emit("Log display cleared")

    def clear_device_buffer(self, serial: str) -> None:
        """Clear the hardware log buffer on the Android device via adb logcat -c."""
        try:
            self.adb.clear_device_logcat(serial)
            self._full_export_buffer.clear()
            self.status_updated.emit("Device log buffer cleared (adb logcat -c)")
        except Exception as e:
            logger.error("Failed to clear device log buffer: %s", e)
            raise
