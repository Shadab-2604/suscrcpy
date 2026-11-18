"""Unit tests for Universal Screen Profiles Library and Profile Manager in SUSCRCPY 2.1."""
import json
import tempfile
import unittest
from pathlib import Path

from core.profile_manager import ProfileManager
from core.profile_model import (
    AspectRatio,
    Density,
    FoldableInfo,
    LogicalViewport,
    Resolution,
    SafeAreas,
    ScreenProfile,
    VALID_CATEGORIES,
    XRInfo,
)


class TestProfileModel(unittest.TestCase):
    def test_all_12_categories_exist(self):
        expected_categories = [
            "smartphone",
            "tablet",
            "foldable",
            "wearable",
            "laptop",
            "monitor",
            "television",
            "gaming",
            "automotive",
            "kiosk",
            "xr",
            "ereader",
        ]
        for cat in expected_categories:
            self.assertIn(cat, VALID_CATEGORIES)

    def test_gcd_aspect_ratio_calculation(self):
        # 1080x1920 -> 9:16
        ar = ScreenProfile.calculate_aspect_ratio(1080, 1920)
        self.assertEqual(ar.width, 9)
        self.assertEqual(ar.height, 16)

        # 1440x2560 -> 9:16
        ar = ScreenProfile.calculate_aspect_ratio(1440, 2560)
        self.assertEqual(ar.width, 9)
        self.assertEqual(ar.height, 16)

        # 1920x1080 -> 16:9
        ar = ScreenProfile.calculate_aspect_ratio(1920, 1080)
        self.assertEqual(ar.width, 16)
        self.assertEqual(ar.height, 9)

        # 1280x800 -> 16:10
        ar = ScreenProfile.calculate_aspect_ratio(1280, 800)
        self.assertEqual(ar.width, 16)
        self.assertEqual(ar.height, 10)

        # Square 450x450 -> 1:1
        ar = ScreenProfile.calculate_aspect_ratio(450, 450)
        self.assertEqual(ar.width, 1)
        self.assertEqual(ar.height, 1)

    def test_window_size_classes(self):
        # Compact (<600dp)
        p_compact = ScreenProfile(
            id="test-compact",
            category="smartphone",
            platform="android",
            manufacturer="Test",
            model="Phone",
            screen_name="Main",
            resolution=Resolution(1080, 2400),
            aspect_ratio=AspectRatio(9, 20),
            density=Density(scale_factor=2.5),
            logical_viewport=LogicalViewport(width_dp=432, height_dp=960),
        )
        w_class, h_class = p_compact.get_window_size_classes()
        self.assertIn("Compact", w_class)
        self.assertIn("Expanded", h_class)

        # Medium (600-839dp)
        p_medium = ScreenProfile(
            id="test-medium",
            category="tablet",
            platform="android",
            manufacturer="Test",
            model="Small Tablet",
            screen_name="Main",
            resolution=Resolution(800, 1280),
            aspect_ratio=AspectRatio(10, 16),
            density=Density(scale_factor=1.33),
            logical_viewport=LogicalViewport(width_dp=601, height_dp=962),
        )
        w_class, _ = p_medium.get_window_size_classes()
        self.assertIn("Medium", w_class)

        # Expanded (840-1199dp)
        p_expanded = ScreenProfile(
            id="test-expanded",
            category="tablet",
            platform="android",
            manufacturer="Test",
            model="Large Tablet",
            screen_name="Main",
            resolution=Resolution(1600, 2560),
            aspect_ratio=AspectRatio(16, 10),
            density=Density(scale_factor=1.75),
            logical_viewport=LogicalViewport(width_dp=914, height_dp=1462),
        )
        w_class, _ = p_expanded.get_window_size_classes()
        self.assertIn("Expanded", w_class)

    def test_foldable_properties(self):
        p_fold = ScreenProfile(
            id="test-fold",
            category="foldable",
            platform="android",
            manufacturer="Test",
            model="Fold Device",
            screen_name="Inner",
            resolution=Resolution(1812, 2176),
            aspect_ratio=AspectRatio(5, 6),
            foldable=FoldableInfo(
                enabled=true if hasattr(self, "true") else True,
                posture="tabletop",
                hinge={"position": 1088, "width": 20, "orientation": "horizontal"},
                display_mode="inner",
            ),
        )
        self.assertTrue(p_fold.foldable.enabled)
        self.assertEqual(p_fold.foldable.posture, "tabletop")
        self.assertEqual(p_fold.foldable.display_mode, "inner")

    def test_xr_properties(self):
        p_xr = ScreenProfile(
            id="test-xr",
            category="xr",
            platform="android",
            manufacturer="Test",
            model="VR Headset",
            screen_name="Dual Eye",
            resolution=Resolution(4128, 2208),
            aspect_ratio=AspectRatio(187, 100),
            xr=XRInfo(
                enabled=True,
                per_eye_width_px=2064,
                per_eye_height_px=2208,
                fov_deg=110.0,
                stereo_mode="side_by_side",
            ),
        )
        self.assertTrue(p_xr.xr.enabled)
        self.assertEqual(p_xr.xr.per_eye_width_px, 2064)
        self.assertEqual(p_xr.xr.fov_deg, 110.0)

    def test_invalid_profile_rejection(self):
        with self.assertRaises(ValueError):
            p = ScreenProfile(
                id="",  # Empty ID must fail
                category="smartphone",
                platform="android",
                manufacturer="Test",
                model="Bad Device",
                screen_name="Main",
                resolution=Resolution(1080, 1920),
                aspect_ratio=AspectRatio(9, 16),
            )
            p.validate()

        with self.assertRaises(ValueError):
            p = ScreenProfile(
                id="valid-id",
                category="invalid_category_xyz",
                platform="android",
                manufacturer="Test",
                model="Bad Category",
                screen_name="Main",
                resolution=Resolution(1080, 1920),
                aspect_ratio=AspectRatio(9, 16),
            )
            p.validate()


class TestProfileManager(unittest.TestCase):
    def setUp(self):
        self.pm = ProfileManager()

    def test_database_loads_all_categories(self):
        profiles = self.pm.get_all_profiles()
        self.assertGreater(len(profiles), 20)

        categories_found = set(p.category for p in profiles)
        for cat in [
            "smartphone",
            "tablet",
            "foldable",
            "wearable",
            "laptop",
            "monitor",
            "television",
            "gaming",
            "automotive",
            "kiosk",
            "xr",
            "ereader",
        ]:
            self.assertIn(cat, categories_found, f"Category '{cat}' must have profiles loaded.")

    def test_search_and_filter(self):
        # Search by model name
        results = self.pm.search_profiles(query="N15")
        self.assertTrue(any(p.id == "smartphone-ikall-n15" for p in results))

        # Search by resolution
        results = self.pm.search_profiles(query="3840x2160")
        self.assertGreater(len(results), 0)

        # Filter by category
        wearables = self.pm.search_profiles(category="wearable")
        self.assertTrue(all(p.category == "wearable" for p in wearables))

    def test_custom_profile_lifecycle(self):
        temp_id = "custom-test-autogen-01"
        p = ScreenProfile(
            id=temp_id,
            category="custom",
            platform="android",
            manufacturer="AutoTest",
            model="Virtual Phone",
            screen_name="Custom Display",
            resolution=Resolution(1080, 2400),
            aspect_ratio=AspectRatio(9, 20),
            profile_source="custom",
        )

        # Save
        self.pm.save_custom_profile(p)
        loaded = self.pm.get_profile_by_id(temp_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.model, "Virtual Phone")

        # Delete
        deleted = self.pm.delete_custom_profile(temp_id)
        self.assertTrue(deleted)
        self.assertIsNone(self.pm.get_profile_by_id(temp_id))


if __name__ == "__main__":
    unittest.main()
