"""Error and Crash Detector for Android Logcat Streams.

Classifies log severity using official Android log priorities, detects confirmed
fatal crashes, ANRs, runtime exceptions, and groups related crash stack traces
without false positives on informational or vendor messages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class LogSeverity(str, Enum):
    VERBOSE = "V"
    DEBUG = "D"
    INFO = "I"
    WARNING = "W"
    ERROR = "E"
    FATAL = "F"


# Regex patterns specifically indicating confirmed fatal crashes and ANRs
CONFIRMED_CRASH_PATTERNS = [
    re.compile(r"FATAL EXCEPTION:\s*", re.IGNORECASE),
    re.compile(r"AndroidRuntime:\s+FATAL EXCEPTION", re.IGNORECASE),
    re.compile(r"Process\s+[a-zA-Z0-9._:]+\s+\(pid\s+\d+\)\s+has died", re.IGNORECASE),
    re.compile(r"ANR in\s+[a-zA-Z0-9._]+", re.IGNORECASE),
    re.compile(r"Application Not Responding:\s*", re.IGNORECASE),
    re.compile(r"Fatal signal\s+\d+\s+\(SIG[A-Z]+\)", re.IGNORECASE),
]

# Standard Java / Android stack trace line pattern
STACK_TRACE_PATTERN = re.compile(r"^\s+(at\s+[a-zA-Z0-9_$.]+\([^\)]+\)|Caused by:)")


@dataclass
class DetectionResult:
    """Analysis result for a single log line."""
    severity: LogSeverity
    is_crash: bool
    is_error: bool
    is_warning: bool
    is_stack_trace: bool
    crash_reason: Optional[str] = None


class ErrorDetector:
    """Analyzes log entries for errors, crashes, and stack trace groupings.

    Follows strict Android log priorities (V, D, I, W, E, F) as the primary classification.
    Informational (I) or Debug (D) messages are never classified as errors merely because
    they contain words like 'error', 'failed', 'invalid', 'cache', or 'exception'.
    """

    def __init__(self) -> None:
        self.error_count = 0
        self.warning_count = 0
        self.crash_count = 0
        self._in_crash_state = False
        self._last_crash_pid: Optional[int] = None

    def reset_counts(self) -> None:
        """Reset error, warning, and crash counters."""
        self.error_count = 0
        self.warning_count = 0
        self.crash_count = 0
        self._in_crash_state = False
        self._last_crash_pid = None

    def analyze(self, level_char: str, tag: str, message: str, pid: Optional[int] = None) -> DetectionResult:
        """Evaluate a log message and return its detection result."""
        char = level_char.upper().strip() if level_char else "I"
        if char == "F":
            severity = LogSeverity.FATAL
        elif char == "E":
            severity = LogSeverity.ERROR
        elif char == "W":
            severity = LogSeverity.WARNING
        elif char == "D":
            severity = LogSeverity.DEBUG
        elif char == "V":
            severity = LogSeverity.VERBOSE
        else:
            severity = LogSeverity.INFO

        combined_text = f"{tag}: {message}"
        is_stack = bool(STACK_TRACE_PATTERN.search(message))
        is_crash = False
        crash_reason = None

        # Check for confirmed crash signatures (only at level E, F, or unhandled crash headers)
        if severity in (LogSeverity.ERROR, LogSeverity.FATAL) or "FATAL" in combined_text.upper():
            for pattern in CONFIRMED_CRASH_PATTERNS:
                if pattern.search(combined_text):
                    is_crash = True
                    crash_reason = pattern.pattern
                    self._in_crash_state = True
                    self._last_crash_pid = pid
                    break

        # Group continuation of stack traces if we are in an active crash sequence
        if not is_crash and is_stack and self._in_crash_state:
            if pid is None or self._last_crash_pid is None or pid == self._last_crash_pid:
                is_crash = True
                crash_reason = "Crash Stack Trace"
        elif not is_stack and severity not in (LogSeverity.ERROR, LogSeverity.FATAL):
            # Normal informational log line ends the active crash sequence
            self._in_crash_state = False
            self._last_crash_pid = None

        # Strictly authoritative classification:
        # A log is an Error IF AND ONLY IF severity is ERROR/FATAL or a confirmed crash.
        # Informational or Debug messages with words like 'cache error' or 'fail' are NEVER errors.
        is_error = (severity in (LogSeverity.ERROR, LogSeverity.FATAL)) or is_crash
        is_warning = (severity == LogSeverity.WARNING) and not is_error

        if is_crash:
            self.crash_count += 1
        elif is_error:
            self.error_count += 1
        elif is_warning:
            self.warning_count += 1

        return DetectionResult(
            severity=severity,
            is_crash=is_crash,
            is_error=is_error,
            is_warning=is_warning,
            is_stack_trace=is_stack,
            crash_reason=crash_reason,
        )
