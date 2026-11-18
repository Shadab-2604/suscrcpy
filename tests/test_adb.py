"""Unit tests for ADB device parsing and commands."""
import unittest
from unittest.mock import MagicMock, patch

from core.adb_manager import AdbError, AdbManager, DeviceItem


class TestAdbManager(unittest.TestCase):
    def setUp(self):
        self.mgr = AdbManager()

    def test_parse_devices_output(self):
        mock_output = (
            "List of devices attached\n"
            "0123456789ABCDEF       device product:iKall_N15 model:iKall_N15 device:iKall transport_id:1\n"
            "192.168.1.100:5555     device product:emulator model:Pixel_4 device:generic transport_id:2\n"
            "UNAUTH123456          unauthorized transport_id:3\n"
        )
        with patch.object(self.mgr, "run") as mock_run, patch.object(self.mgr, "start_server"):
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
            devices = self.mgr.list_devices()

        self.assertEqual(len(devices), 3)
        self.assertEqual(devices[0].serial, "0123456789ABCDEF")
        self.assertEqual(devices[0].model, "iKall_N15")
        self.assertTrue(devices[0].is_authorized)
        self.assertTrue(devices[0].is_usb)

        self.assertEqual(devices[1].serial, "192.168.1.100:5555")
        self.assertFalse(devices[1].is_usb)

        self.assertEqual(devices[2].serial, "UNAUTH123456")
        self.assertFalse(devices[2].is_authorized)

    def test_parse_display_size(self):
        wm_output = (
            "Physical size: 720x1600\n"
            "Override size: 1080x2400\n"
        )
        with patch.object(self.mgr, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=wm_output)
            phys, override = self.mgr.get_display_size("dummy_serial")

        self.assertEqual(phys, (720, 1600))
        self.assertEqual(override, (1080, 2400))

    def test_parse_native_display_size_without_override(self):
        wm_output = "Physical size: 720x1600\n"
        with patch.object(self.mgr, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=wm_output)
            phys, override = self.mgr.get_display_size("dummy_serial")

        self.assertEqual(phys, (720, 1600))
        self.assertIsNone(override)

    def test_serial_targeting(self):
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="", stderr="")
            self.mgr.run(["shell", "echo", "test"], serial="DEVICE_XYZ")
            called_args = mock_sub.call_args[0][0]
            self.assertIn("-s", called_args)
            self.assertIn("DEVICE_XYZ", called_args)


if __name__ == "__main__":
    unittest.main()
