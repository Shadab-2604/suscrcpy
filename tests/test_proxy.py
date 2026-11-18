"""Unit tests for Network Proxy Manager."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from PySide6.QtGui import QGuiApplication

from core.adb_manager import AdbManager
from core.proxy_manager import ProxyManager


class TestProxyManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QGuiApplication.instance():
            cls.app = QGuiApplication([])

    def setUp(self):
        self.mock_adb = MagicMock(spec=AdbManager)
        self.proxy_mgr = ProxyManager(self.mock_adb)

    def test_get_device_proxy_configured(self):
        self.mock_adb.run.return_value = "192.168.1.150:8080\n"
        config = self.proxy_mgr.get_device_proxy("TEST_SERIAL")

        self.assertTrue(config.is_enabled)
        self.assertEqual(config.host, "192.168.1.150")
        self.assertEqual(config.port, 8080)

    def test_get_device_proxy_disabled(self):
        self.mock_adb.run.return_value = "null\n"
        config = self.proxy_mgr.get_device_proxy("TEST_SERIAL")

        self.assertFalse(config.is_enabled)

    def test_set_device_proxy(self):
        self.mock_adb.run.return_value = ""
        ok, msg = self.proxy_mgr.set_device_proxy("TEST_SERIAL", "10.0.0.5", 8888)

        self.assertTrue(ok)
        self.mock_adb.run.assert_called_with(
            ["shell", "settings", "put", "global", "http_proxy", "10.0.0.5:8888"],
            serial="TEST_SERIAL",
        )
        self.assertEqual(self.proxy_mgr.current_config.host, "10.0.0.5")
        self.assertEqual(self.proxy_mgr.current_config.port, 8888)

    def test_clear_device_proxy(self):
        self.mock_adb.run.return_value = ""
        ok, msg = self.proxy_mgr.clear_device_proxy("TEST_SERIAL")

        self.assertTrue(ok)
        self.assertFalse(self.proxy_mgr.current_config.is_enabled)


if __name__ == "__main__":
    unittest.main()
