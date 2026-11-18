"""Unit tests for cryptographic verification and archive security in SUSCRCPY."""
import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from update_manager import ArchiveSecurityError, UpdateManager


class TestChecksumsAndArchiveSecurity(unittest.TestCase):
    """Test suite for SHA-256 integrity checks and Zip Slip security validation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_calculate_sha256(self) -> None:
        test_file = self.temp_path / "sample.txt"
        content = b"SUSCRCPY secure test content 12345"
        test_file.write_bytes(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        actual_hash = UpdateManager.calculate_sha256(test_file)
        self.assertEqual(actual_hash, expected_hash)

    def test_parse_checksums_file(self) -> None:
        raw_sums = (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  empty.txt\n"
            "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b *suscrcpy-source.zip\n"
            "# Comment line\n"
            "\n"
        )
        parsed = UpdateManager.parse_checksums_file(raw_sums)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed["suscrcpy-source.zip"], "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b")
        self.assertEqual(parsed["empty.txt"], "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")

    def test_valid_zip_archive_passes(self) -> None:
        zip_path = self.temp_path / "valid.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("main.py", "print('hello')")
            z.writestr("core/test.py", "pass")

        extract_dest = self.temp_path / "dest"
        extract_dest.mkdir()
        with zipfile.ZipFile(zip_path, "r") as z:
            # Should not raise exception
            UpdateManager.validate_zip_members(z, extract_dest)

    def test_zip_slip_absolute_path_rejected(self) -> None:
        zip_path = self.temp_path / "malicious_abs.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("/etc/passwd", "root:x:0:0")

        extract_dest = self.temp_path / "dest"
        extract_dest.mkdir()
        with zipfile.ZipFile(zip_path, "r") as z:
            with self.assertRaises(ArchiveSecurityError):
                UpdateManager.validate_zip_members(z, extract_dest)

    def test_zip_slip_parent_traversal_rejected(self) -> None:
        zip_path = self.temp_path / "malicious_traversal.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("../../shadow.txt", "stolen_data")

        extract_dest = self.temp_path / "dest"
        extract_dest.mkdir()
        with zipfile.ZipFile(zip_path, "r") as z:
            with self.assertRaises(ArchiveSecurityError):
                UpdateManager.validate_zip_members(z, extract_dest)


if __name__ == "__main__":
    unittest.main()
