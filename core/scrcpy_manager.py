"""Scrcpy process management for SUSCRCPY.

Handles scrcpy executable discovery, unique window title generation, process lifecycle,
and crash monitoring.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from core.process_manager import ProcessManager

logger = logging.getLogger("suscrcpy.scrcpy_manager")


class ScrcpyError(RuntimeError):
    """Raised when scrcpy execution fails."""
    pass


class ScrcpyManager(QObject):
    """Manages the lifecycle of the scrcpy mirroring process."""

    started = Signal(str)  # unique window title
    stopped = Signal(int)  # exit code
    crashed = Signal(str)  # crash explanation
    stream_dimensions_changed = Signal(int, int)  # width, height
    stream_fps_reported = Signal(float)           # live fps

    def __init__(
        self,
        custom_scrcpy_path: Optional[str] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._custom_scrcpy_path = custom_scrcpy_path
        self._scrcpy_path = self.locate_scrcpy()
        self._current_proc: Optional[subprocess.Popen] = None
        self._current_title: Optional[str] = None
        self._current_serial: Optional[str] = None
        self._current_quality: str = "balanced"
        self._current_borderless: bool = True
        self._stream_width: int = 0
        self._stream_height: int = 0
        self._reader_thread: Optional[Any] = None

    @property
    def stream_dimensions(self) -> Tuple[int, int]:
        return (self._stream_width, self._stream_height)

    @property
    def stream_width(self) -> int:
        return self._stream_width

    @property
    def stream_height(self) -> int:
        return self._stream_height

    @property
    def current_quality(self) -> str:
        return self._current_quality

    def set_custom_scrcpy_path(self, path: Optional[str]) -> None:
        """Set a user-specified path to the scrcpy binary."""
        self._custom_scrcpy_path = path
        self._scrcpy_path = self.locate_scrcpy()

    @property
    def scrcpy_path(self) -> str:
        return self._scrcpy_path

    @property
    def current_proc(self) -> Optional[subprocess.Popen]:
        return self._current_proc

    @property
    def current_title(self) -> Optional[str]:
        return self._current_title

    def locate_scrcpy(self) -> str:
        """Find the scrcpy binary across environment and standard paths."""
        if self._custom_scrcpy_path and os.path.isfile(self._custom_scrcpy_path):
            return self._custom_scrcpy_path

        env_scrcpy = os.environ.get("SCRCPY_PATH")
        if env_scrcpy and os.path.isfile(env_scrcpy):
            return env_scrcpy

        which_scrcpy = shutil.which("scrcpy")
        if which_scrcpy:
            return which_scrcpy

        # Common Windows paths
        win_candidates = [
            os.path.expandvars(r"%PROGRAMFILES%\scrcpy\scrcpy.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\scrcpy\scrcpy.exe"),
            r"C:\scrcpy\scrcpy.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\scrcpy\scrcpy.exe"),
        ]
        # Common Linux paths
        linux_candidates = [
            "/usr/bin/scrcpy",
            "/usr/local/bin/scrcpy",
            "/snap/bin/scrcpy",
            os.path.expanduser("~/.local/bin/scrcpy"),
        ]

        candidates = win_candidates if sys.platform.startswith("win") else linux_candidates
        for candidate in candidates:
            if os.path.isfile(candidate) and (sys.platform.startswith("win") or os.access(candidate, os.X_OK)):
                return candidate

        return "scrcpy"

    def set_quality_profile(self, profile: str) -> None:
        """Set the video stream quality profile (performance, balanced, high)."""
        self._current_quality = profile
        logger.info("Scrcpy stream quality set to: %s", profile)

    def is_running(self) -> bool:
        """Check if scrcpy process is actively running."""
        return self._current_proc is not None and self._current_proc.poll() is None

    def start(
        self,
        serial: str,
        borderless: bool = True,
        quality_profile: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
    ) -> Tuple[subprocess.Popen, str]:
        """Start a new scrcpy session with a unique window title and configured stream profile."""
        if self.is_running():
            self.stop()

        if quality_profile:
            self._current_quality = quality_profile
        self._current_borderless = borderless

        unique_id = uuid.uuid4().hex[:8]
        window_title = f"suscrcpy_embed_{unique_id}"
        self._current_title = window_title
        self._current_serial = serial

        cmd = [
            self._scrcpy_path,
            "--serial",
            serial,
            "--window-title",
            window_title,
            "--stay-awake",
        ]

        # Apply streaming quality profiles
        if self._current_quality == "performance":
            cmd.extend(["--max-size=720", "--video-bit-rate=4M", "--max-fps=30"])
        elif self._current_quality == "high":
            cmd.extend(["--video-bit-rate=16M", "--max-fps=60"])
        else:  # balanced (default)
            cmd.extend(["--max-size=1080", "--video-bit-rate=8M", "--max-fps=60"])

        if borderless:
            cmd.append("--window-borderless")

        if extra_args:
            cmd.extend(extra_args)

        env = os.environ.copy()
        # On Linux, enforce X11 driver for SDL when DISPLAY is available so XWayland reparenting succeeds
        if sys.platform.startswith("linux") and "DISPLAY" in env:
            env["SDL_VIDEODRIVER"] = "x11"

        try:
            logger.info("Spawning scrcpy: %s", " ".join(cmd))
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout for unified parsing
                env=env,
                text=True,
                bufsize=1,
                start_new_session=(not sys.platform.startswith("win")),
            )
            self._current_proc = proc
            ProcessManager.instance().register(proc)

            # Spawn reader thread to capture stream dimensions and texture changes
            reader = threading.Thread(target=self._read_stdout, args=(proc,), daemon=True)
            self._reader_thread = reader
            reader.start()

            self.started.emit(window_title)
            return proc, window_title
        except FileNotFoundError as e:
            raise ScrcpyError(f"scrcpy executable not found at '{self._scrcpy_path}'.") from e
        except Exception as e:
            raise ScrcpyError(f"Failed to start scrcpy: {e}") from e

    def _read_stdout(self, proc: subprocess.Popen) -> None:
        """Read scrcpy stdout/stderr in real time to capture stream dimensions and fps."""
        texture_pattern = re.compile(r"Texture:\s*(\d+)x(\d+)")
        fps_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*fps")

        try:
            if not proc.stdout:
                return
            for line in proc.stdout:
                line_str = line.strip()
                if not line_str:
                    continue
                # Match texture resolution changes (e.g. "INFO: Texture: 800x1280")
                m_tex = texture_pattern.search(line_str)
                if m_tex:
                    w = int(m_tex.group(1))
                    h = int(m_tex.group(2))
                    logger.info("Scrcpy stream texture detected: %dx%d", w, h)
                    self._stream_width = w
                    self._stream_height = h
                    self.stream_dimensions_changed.emit(w, h)

                # Match live fps if reported
                m_fps = fps_pattern.search(line_str)
                if m_fps:
                    fps = float(m_fps.group(1))
                    self.stream_fps_reported.emit(fps)
        except Exception as e:
            logger.debug("Scrcpy stdout reader closed: %s", e)

    def stop(self, timeout: float = 3.0) -> None:
        """Safely stop the scrcpy process."""
        proc = self._current_proc
        self._current_proc = None
        self._current_title = None

        if proc is not None:
            ProcessManager.instance().stop_process(proc, timeout=timeout)
            exit_code = proc.poll() if proc.poll() is not None else 0
            self.stopped.emit(exit_code)

    def restart(self, serial: Optional[str] = None) -> Tuple[subprocess.Popen, str]:
        """Restart scrcpy session for the target device preserving stream quality."""
        target_serial = serial or self._current_serial
        if not target_serial:
            raise ScrcpyError("Cannot restart scrcpy: no serial provided.")
        self.stop()
        time.sleep(0.35)  # Allow port and socket release
        return self.start(
            target_serial,
            borderless=self._current_borderless,
            quality_profile=self._current_quality,
        )
