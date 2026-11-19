"""Exactness tests for log capture classification, counters, filters and export."""
import tempfile
import unittest

from core.error_detector import ErrorDetector, LogSeverity
from core.log_exporter import LogExporter
from core.log_manager import LogEntry
from ui.logs_panel import matches_category
from core.log_manager import THREADTIME_REGEX


def _entry(detector, level, tag, message, pid=100, raw=None):
    detection = detector.analyze(level, tag, message, pid=pid)
    return LogEntry(
        timestamp="11-18 10:00:00.000",
        pid=pid,
        tid=pid,
        level=detection.severity.value,
        tag=tag,
        message=message,
        raw=raw or f"11-18 10:00:00.000 {pid:5d} {pid:5d} {level} {tag}: {message}",
        detection=detection,
    )


class TestLogAccuracy(unittest.TestCase):
    def setUp(self):
        self.detector = ErrorDetector()

    def test_priority_mapping_is_exact(self):
        expected = {
            "V": LogSeverity.VERBOSE,
            "D": LogSeverity.DEBUG,
            "I": LogSeverity.INFO,
            "W": LogSeverity.WARNING,
            "E": LogSeverity.ERROR,
            "F": LogSeverity.FATAL,
        }
        for char, severity in expected.items():
            self.assertEqual(self.detector.analyze(char, "Tag", "text").severity, severity)

    def test_warning_never_counts_as_error(self):
        result = self.detector.analyze("W", "Net", "Slow link")
        self.assertTrue(result.is_warning)
        self.assertFalse(result.is_error)
        self.assertEqual(self.detector.warning_count, 1)
        self.assertEqual(self.detector.error_count, 0)

    def test_crash_is_one_event_but_every_frame_is_an_error_line(self):
        self.detector.analyze("E", "AndroidRuntime", "FATAL EXCEPTION: main", pid=42)
        for _ in range(5):
            self.detector.analyze(
                "E", "AndroidRuntime", "    at com.example.Main.onCreate(Main.java:10)", pid=42
            )

        self.assertEqual(self.detector.crash_count, 1, "stack frames must not inflate crash count")
        self.assertEqual(self.detector.error_count, 6, "all error-level lines must be counted")
        self.assertEqual(self.detector.warning_count, 0)

    def test_anr_and_process_death_are_crash_events(self):
        self.detector.analyze("E", "ActivityManager", "ANR in com.example.app", pid=7)
        self.detector.analyze("E", "ActivityManager", "Process com.example.app (pid 7) has died", pid=7)
        self.assertEqual(self.detector.crash_count, 2)

    def test_info_and_debug_are_never_errors(self):
        for level, message in (
            ("I", "Cache miss for error_fallback"),
            ("D", "Token validation failed gracefully"),
            ("I", "Handled NullPointerException locally"),
            ("V", "retry count 3"),
        ):
            result = self.detector.analyze(level, "App", message)
            self.assertFalse(result.is_error, message)
            self.assertFalse(result.is_warning, message)
        self.assertEqual(self.detector.error_count, 0)
        self.assertEqual(self.detector.warning_count, 0)

    def test_continuation_line_parsing_keeps_raw_text(self):
        raw = "11-18 10:20:30.123  1234  1245 E AndroidRuntime: FATAL EXCEPTION: main"
        match = THREADTIME_REGEX.match(raw)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(5).strip(), "AndroidRuntime")

    def test_category_filters_match_detection_flags(self):
        info = _entry(self.detector, "I", "App", "started")
        warning = _entry(self.detector, "W", "App", "slow")
        error = _entry(self.detector, "E", "App", "failed")
        crash = _entry(self.detector, "E", "AndroidRuntime", "FATAL EXCEPTION: main")

        self.assertTrue(matches_category(info, "all"))
        self.assertFalse(matches_category(info, "error"))

        self.assertTrue(matches_category(warning, "warning"))
        self.assertFalse(matches_category(warning, "error"))

        self.assertTrue(matches_category(error, "error"))
        self.assertTrue(matches_category(crash, "error"), "crash lines are error-level")
        self.assertTrue(matches_category(crash, "crash"))
        self.assertFalse(matches_category(error, "crash"))

    def test_filtered_export_records_scope(self):
        entries = [_entry(self.detector, "W", "App", "slow link")]
        with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
            path = tmp.name

        count = LogExporter.export_to_file(
            filepath=path,
            logs=entries,
            details=None,
            mode="Full Device",
            warning_count=1,
            filter_label="Warning",
        )
        self.assertEqual(count, 1)
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Export Scope     : Warning only", content)
        self.assertIn("Warnings         : 1", content)


if __name__ == "__main__":
    unittest.main()
