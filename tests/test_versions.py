"""Unit tests for semantic versioning in SUSCRCPY."""
import unittest

from version import APP_VERSION, is_newer_version, parse_semver


class TestVersionManagement(unittest.TestCase):
    """Test suite for semantic version parsing and comparison."""

    def test_parse_semver_basic(self) -> None:
        self.assertEqual(parse_semver("1.0.0"), (1, 0, 0, 1, ""))
        self.assertEqual(parse_semver("v2.1.0"), (2, 1, 0, 1, ""))
        self.assertEqual(parse_semver("  v0.9.5  "), (0, 9, 5, 1, ""))

    def test_parse_semver_prerelease(self) -> None:
        parsed = parse_semver("v2.1.0-beta.1")
        self.assertEqual(parsed, (2, 1, 0, 0, "beta.1"))

    def test_version_comparisons(self) -> None:
        self.assertTrue(is_newer_version("2.1.1", "2.1.0"))
        self.assertTrue(is_newer_version("3.0.0", "2.9.9"))
        self.assertTrue(is_newer_version("2.2.0", "2.1.9"))

        # Older or equal versions should return False
        self.assertFalse(is_newer_version("2.1.0", "2.1.0"))
        self.assertFalse(is_newer_version("2.0.9", "2.1.0"))
        self.assertFalse(is_newer_version("1.9.9", "2.0.0"))

    def test_final_versus_prerelease_comparison(self) -> None:
        # Final release should be considered newer than prerelease of same version
        self.assertTrue(is_newer_version("2.1.0", "2.1.0-rc1"))
        self.assertFalse(is_newer_version("2.1.0-rc1", "2.1.0"))

    def test_app_version_is_valid_semver(self) -> None:
        parsed = parse_semver(APP_VERSION)
        self.assertGreaterEqual(parsed[0], 1)
        self.assertGreaterEqual(parsed[1], 0)


if __name__ == "__main__":
    unittest.main()
