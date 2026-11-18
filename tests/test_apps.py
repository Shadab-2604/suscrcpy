"""Unit tests for installed Android applications discovery and filtering."""
import unittest
from unittest.mock import MagicMock

from core.app_manager import AppInfo, AppManager


class DummyAdbApps:
    def list_packages(self, serial, filter_type="all"):
        if filter_type == "user":
            return ["com.example.myapp", "in.meg.app"]
        elif filter_type == "system":
            return ["com.android.settings", "com.android.systemui"]
        return ["com.example.myapp", "in.meg.app", "com.android.settings", "com.android.systemui"]

    def get_package_version_info(self, serial, package_name):
        if package_name == "in.meg.app":
            return "2.1.0", "142"
        return "1.0.0", "1"


class TestAppManager(unittest.TestCase):
    def setUp(self):
        self.adb = DummyAdbApps()
        self.mgr = AppManager(self.adb)

    def test_load_and_categorize_apps(self):
        apps = self.mgr.load_applications("TEST_SERIAL", force_refresh=True)
        self.assertEqual(len(apps), 4)

        user_apps = [a for a in apps if not a.is_system]
        system_apps = [a for a in apps if a.is_system]

        self.assertEqual(len(user_apps), 2)
        self.assertEqual(len(system_apps), 2)
        self.assertTrue(any(a.package_name == "in.meg.app" for a in user_apps))

    def test_filter_apps_by_search_and_category(self):
        apps = [
            AppInfo(package_name="in.meg.app", app_name="MegApp", is_system=False),
            AppInfo(package_name="com.test.demo", app_name="DemoApp", is_system=False),
            AppInfo(package_name="com.android.settings", app_name="Settings", is_system=True),
        ]

        # Filter: User only
        user_only = self.mgr.filter_apps(apps, category="user")
        self.assertEqual(len(user_only), 2)

        # Filter: System only
        sys_only = self.mgr.filter_apps(apps, category="system")
        self.assertEqual(len(sys_only), 1)

        # Search query
        searched = self.mgr.filter_apps(apps, query="meg")
        self.assertEqual(len(searched), 1)
        self.assertEqual(searched[0].package_name, "in.meg.app")

    def test_enrich_details(self):
        app = AppInfo(package_name="in.meg.app", app_name="MegApp", is_system=False)
        enriched = self.mgr.enrich_app_details("TEST_SERIAL", app)
        self.assertEqual(enriched.version_name, "2.1.0")
        self.assertEqual(enriched.version_code, "142")


if __name__ == "__main__":
    unittest.main()
