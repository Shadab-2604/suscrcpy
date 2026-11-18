"""Process lifecycle manager for SUSCRCPY.

Guarantees clean process cleanup and prevents orphaned processes.
"""
from __future__ import annotations

import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
from typing import List, Optional

logger = logging.getLogger("suscrcpy.process_manager")


class ProcessManager:
    """Tracks and cleans up subprocesses spawned by the application."""

    _instance: Optional[ProcessManager] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._processes: List[subprocess.Popen] = []
        self._cleaned_up = False
        atexit.register(self.cleanup_all)
        self._register_signals()

    @classmethod
    def instance(cls) -> ProcessManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = ProcessManager()
            return cls._instance

    def _register_signals(self) -> None:
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, AttributeError):
            # Not in main thread or signal unsupported on current runtime
            pass

    def _handle_signal(self, signum: int, frame) -> None:
        logger.info("Received termination signal %d, cleaning up processes...", signum)
        self.cleanup_all()
        sys.exit(0)

    def register(self, proc: subprocess.Popen) -> subprocess.Popen:
        """Register a subprocess for lifecycle management."""
        with self._lock:
            if proc not in self._processes:
                self._processes.append(proc)
        return proc

    def unregister(self, proc: subprocess.Popen) -> None:
        """Unregister a process that has already finished cleanly."""
        with self._lock:
            if proc in self._processes:
                self._processes.remove(proc)

    def stop_process(self, proc: Optional[subprocess.Popen], timeout: float = 3.0) -> None:
        """Safely terminate a single process with a kill fallback."""
        if proc is None or proc.poll() is not None:
            return

        try:
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("Process %d did not terminate in time; killing...", proc.pid)
                proc.kill()
                proc.wait(timeout=2.0)
        except (ProcessLookupError, OSError):
            pass
        finally:
            self.unregister(proc)

    def cleanup_all(self) -> None:
        """Terminate all registered processes."""
        with self._lock:
            if self._cleaned_up:
                return
            self._cleaned_up = True
            procs = list(self._processes)
            self._processes.clear()

        for proc in procs:
            if proc and proc.poll() is None:
                try:
                    logger.info("Cleaning up child process PID %d", proc.pid)
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=1.0)
                except Exception as e:
                    logger.debug("Error while terminating process %d: %s", proc.pid, e)
