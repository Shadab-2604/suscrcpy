"""Unit tests for logcat parsing, error detection, and log export."""
import tempfile
import unittest

from core.error_detector import ErrorDetector, LogSeverity
from core.log_exporter import LogExporter
from core.log_manager import LogEntry, THREADTIME_REGEX


class TestLogs(unittest.TestCase):
    def setUp(self):
        self.detector = ErrorDetector()

    def test_threadtime_regex_parsing(self):
        line = "11-18 10:20:30.123  1234  1245 E AndroidRuntime: FATAL EXCEPTION: main"
        match = THREADTIME_REGEX.match(line)
        self.assertIsNotNone(match)
        ts, pid, tid, level, tag, msg = match.groups()
        self.assertEqual(ts, "11-18 10:20:30.123")
        self.assertEqual(int(pid), 1234)
        self.assertEqual(int(tid), 1245)
        self.assertEqual(level, "E")
        self.assertEqual(tag, "AndroidRuntime")
        self.assertEqual(msg, "FATAL EXCEPTION: main")

    def test_error_severity_detection(self):
        res_info = self.detector.analyze("I", "MainActivity", "App started")
        self.assertEqual(res_info.severity, LogSeverity.INFO)
        self.assertFalse(res_info.is_error)
        self.assertFalse(res_info.is_crash)

        res_warn = self.detector.analyze("W", "Network", "Slow connection detected")
        self.assertEqual(res_warn.severity, LogSeverity.WARNING)
        self.assertTrue(res_warn.is_warning)
        self.assertFalse(res_warn.is_crash)

        res_err = self.detector.analyze("E", "Database", "Failed to query SQLite")
        self.assertEqual(res_err.severity, LogSeverity.ERROR)
        self.assertTrue(res_err.is_error)
        self.assertFalse(res_err.is_crash)

    def test_crash_pattern_and_stack_trace_grouping(self):
        # 1. Trigger crash line
        res_crash = self.detector.analyze(
            "E", "AndroidRuntime", "FATAL EXCEPTION: main", pid=5000
        )
        self.assertTrue(res_crash.is_crash)
        self.assertEqual(self.detector.crash_count, 1)

        # 2. Subsequent stack trace lines for same PID should be grouped with crash
        stack_line = "    at in.meg.app.MainActivity.onCreate(MainActivity.java:45)"
        res_stack = self.detector.analyze("E", "AndroidRuntime", stack_line, pid=5000)
        self.assertTrue(res_stack.is_crash)
        self.assertTrue(res_stack.is_stack_trace)

    def test_log_export(self):
        entries = [
            LogEntry(
                timestamp="11-18 10:00:00.001",
                pid=100,
                tid=100,
                level="I",
                tag="App",
                message="Init",
                raw="11-18 10:00:00.001   100   100 I App: Init",
                detection=self.detector.analyze("I", "App", "Init"),
            ),
            LogEntry(
                timestamp="11-18 10:00:01.002",
                pid=100,
                tid=100,
                level="E",
                tag="App",
                message="Fatal error",
                raw="11-18 10:00:01.002   100   100 E App: Fatal error",
                detection=self.detector.analyze("E", "App", "Fatal error"),
            ),
        ]

        with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
            filepath = tmp.name

        count = LogExporter.export_to_file(
            filepath=filepath,
            logs=entries,
            details=None,
            mode="Full Device",
            error_count=1,
            warning_count=0,
            crash_count=0,
        )
        self.assertEqual(count, 2)

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("SUSCRCPY 2.0.0 — Android Device Log Export", content)
        self.assertIn("SECURITY NOTICE:", content)
        self.assertIn("11-18 10:00:00.001   100   100 I App: Init", content)


if __name__ == "__main__":
    unittest.main()
