"""Tests for APK path validation and exact adb install-output parsing."""
import os
import tempfile
import unittest

from core.apk_installer import (
    ApkInstallError,
    InstallResult,
    parse_install_output,
    validate_apk_path,
)


class TestValidateApkPath(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".apk", delete=False)
        self._tmp.write(b"PK\x03\x04 fake apk")
        self._tmp.close()

    def tearDown(self):
        os.unlink(self._tmp.name)

    def test_accepts_existing_apk(self):
        resolved = validate_apk_path(self._tmp.name)
        self.assertTrue(resolved.is_file())

    def test_accepts_quoted_and_padded_path(self):
        self.assertEqual(
            validate_apk_path(f'  "{self._tmp.name}" '), validate_apk_path(self._tmp.name)
        )

    def test_rejects_empty_path(self):
        with self.assertRaises(ApkInstallError):
            validate_apk_path("   ")

    def test_rejects_missing_file(self):
        with self.assertRaises(ApkInstallError):
            validate_apk_path("/nonexistent/does-not-exist.apk")

    def test_rejects_non_apk_extension(self):
        other = self._tmp.name.replace(".apk", ".zip")
        os.rename(self._tmp.name, other)
        try:
            with self.assertRaises(ApkInstallError):
                validate_apk_path(other)
        finally:
            os.rename(other, self._tmp.name)


class TestParseInstallOutput(unittest.TestCase):
    def test_success_line(self):
        result = parse_install_output(0, "Performing Streamed Install\nSuccess\n", "")
        self.assertIsInstance(result, InstallResult)
        self.assertTrue(result.success)
        self.assertIn("Success", result.output)

    def test_failure_is_reported_with_reason(self):
        output = (
            "Performing Streamed Install\n"
            "adb: failed to install traky.apk: Failure "
            "[INSTALL_FAILED_INSUFFICIENT_STORAGE]\n"
        )
        result = parse_install_output(1, output, "")
        self.assertFalse(result.success)
        self.assertIn("storage", result.message.lower())

    def test_unknown_failure_falls_back_to_adb_line(self):
        output = "adb: failed to install traky.apk: error: device offline\n"
        result = parse_install_output(1, "", output)
        self.assertFalse(result.success)
        self.assertIn("device offline", result.message)

    def test_success_word_in_failure_output_never_passes(self):
        output = "Failure [INSTALL_FAILED_ALREADY_EXISTS] some success text\n"
        result = parse_install_output(1, output, "")
        self.assertFalse(result.success)

    def test_nonzero_exit_without_text(self):
        result = parse_install_output(1, "", "")
        self.assertFalse(result.success)
        self.assertIn("1", result.message)


if __name__ == "__main__":
    unittest.main()
