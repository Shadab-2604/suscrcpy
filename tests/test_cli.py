"""Unit tests for CLI parsing and arguments in SUSCRCPY."""
import subprocess
import sys
import unittest
from unittest.mock import patch

import main


class TestCommandLineInterface(unittest.TestCase):
    """Test suite for CLI argument parser and commands."""

    def test_version_flag_output(self) -> None:
        from version import APP_VERSION
        res = subprocess.run(
            [sys.executable, "main.py", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("SUSCRCPY", res.stdout)
        self.assertIn(APP_VERSION, res.stdout)

    def test_help_flag_output(self) -> None:
        res = subprocess.run(
            [sys.executable, "main.py", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--check-updates", res.stdout)
        self.assertIn("--update", res.stdout)
        self.assertIn("--adb", res.stdout)
        self.assertIn("--scrcpy", res.stdout)

    def test_parse_args_options(self) -> None:
        with patch.object(sys, "argv", ["main.py", "--debug", "--adb", "/usr/bin/adb", "--scrcpy", "/usr/bin/scrcpy"]):
            args = main.parse_args()
            self.assertTrue(args.debug)
            self.assertEqual(args.adb, "/usr/bin/adb")
            self.assertEqual(args.scrcpy, "/usr/bin/scrcpy")
            self.assertFalse(args.check_updates)
            self.assertFalse(args.update)

    def test_parse_args_check_updates(self) -> None:
        with patch.object(sys, "argv", ["main.py", "--check-updates"]):
            args = main.parse_args()
            self.assertTrue(args.check_updates)
            self.assertFalse(args.update)

    def test_parse_args_update(self) -> None:
        with patch.object(sys, "argv", ["main.py", "--update"]):
            args = main.parse_args()
            self.assertTrue(args.update)
            self.assertFalse(args.check_updates)


if __name__ == "__main__":
    unittest.main()
