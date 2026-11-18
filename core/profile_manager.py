"""Profile Manager and Database Service for SUSCRCPY 2.1.

Loads screen profiles from JSON directories, provides hierarchical browsing,
fuzzy search, validation, custom profile persistence, and import/export.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal

from core.profile_model import CATEGORY_LABELS, ScreenProfile, VALID_CATEGORIES

logger = logging.getLogger("suscrcpy.profile_manager")


class ProfileManager(QObject):
    """Manages loading, searching, persisting, and exporting screen profiles."""

    profiles_loaded = Signal(int)  # count
    profile_added = Signal(object)  # ScreenProfile
    profile_deleted = Signal(str)  # profile_id
    favorites_changed = Signal()

    def __init__(self, base_profiles_dir: Optional[str] = None, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        if base_profiles_dir:
            self._base_dir = Path(base_profiles_dir)
        else:
            # Default to resources/screen_profiles next to source
            self._base_dir = Path(__file__).resolve().parent.parent / "resources" / "screen_profiles"

        # User persistent settings directory
        if sys.platform.startswith("win"):
            self._user_data_dir = Path(os.environ.get("APPDATA", Path.home())) / "suscrcpy"
        else:
            self._user_data_dir = Path.home() / ".suscrcpy"

        self._user_data_dir.mkdir(parents=True, exist_ok=True)
        self._custom_dir = self._base_dir / "custom"
        self._custom_dir.mkdir(parents=True, exist_ok=True)

        self._profiles: Dict[str, ScreenProfile] = {}
        self._favorites: Set[str] = set()
        self._recents: List[str] = []

        self._load_favorites_and_recents()
        self.reload_all_profiles()

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def reload_all_profiles(self) -> int:
        """Scan profile JSON files from all category directories and load them."""
        self._profiles.clear()
        if not self._base_dir.exists():
            logger.warning("Base profiles directory does not exist: %s", self._base_dir)
            return 0

        loaded_count = 0
        for json_path in self._base_dir.rglob("*.json"):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Support either single profile dict or list of profiles
                if isinstance(data, list):
                    for item in data:
                        p = ScreenProfile.from_dict(item)
                        self._profiles[p.id] = p
                        loaded_count += 1
                elif isinstance(data, dict):
                    p = ScreenProfile.from_dict(data)
                    self._profiles[p.id] = p
                    loaded_count += 1
            except Exception as e:
                logger.error("Failed to load profile file %s: %s", json_path, e)

        logger.info("Successfully loaded %d screen profiles.", loaded_count)
        self.profiles_loaded.emit(loaded_count)
        return loaded_count

    def get_all_profiles(self) -> List[ScreenProfile]:
        """Return all loaded profiles sorted by category and model name."""
        return sorted(self._profiles.values(), key=lambda p: (p.category, p.manufacturer, p.model))

    def get_profile_by_id(self, profile_id: str) -> Optional[ScreenProfile]:
        return self._profiles.get(profile_id)

    def get_profiles_by_category(self, category: str) -> List[ScreenProfile]:
        return [p for p in self._profiles.values() if p.category == category]

    def build_hierarchy_tree(self, filter_query: str = "", category_filter: Optional[str] = None) -> Dict[str, Any]:
        """Build hierarchical tree structure for browsing:
        Category -> Platform -> Manufacturer -> Model -> [Profiles]
        """
        tree: Dict[str, Any] = {}
        filtered = self.search_profiles(query=filter_query, category=category_filter)

        for p in filtered:
            cat_label = CATEGORY_LABELS.get(p.category, p.category.title())
            platform_label = p.platform.title()
            mfg_label = p.manufacturer or "Generic"
            model_label = p.model

            if cat_label not in tree:
                tree[cat_label] = {}
            if platform_label not in tree[cat_label]:
                tree[cat_label][platform_label] = {}
            if mfg_label not in tree[cat_label][platform_label]:
                tree[cat_label][platform_label][mfg_label] = {}
            if model_label not in tree[cat_label][platform_label][mfg_label]:
                tree[cat_label][platform_label][mfg_label][model_label] = []

            tree[cat_label][platform_label][mfg_label][model_label].append(p)

        return tree

    def search_profiles(
        self,
        query: str = "",
        category: Optional[str] = None,
        platform: Optional[str] = None,
        size_class: Optional[str] = None,
        verified_only: bool = False,
    ) -> List[ScreenProfile]:
        """Filter profiles across metadata: category, manufacturer, resolution, aspect ratio, size class."""
        query = query.strip().lower()
        results: List[ScreenProfile] = []

        for p in self._profiles.values():
            if category and p.category != category:
                continue
            if platform and p.platform.lower() != platform.lower():
                continue
            if verified_only and not p.verified:
                continue

            if size_class:
                w_class, _ = p.get_window_size_classes()
                if size_class.lower() not in w_class.lower():
                    continue

            if query:
                # Search across id, model, manufacturer, platform, resolution, aspect ratio
                search_corpus = (
                    f"{p.id} {p.model} {p.manufacturer} {p.platform} {p.category} "
                    f"{p.screen_name} {p.resolution.width_px}x{p.resolution.height_px} "
                    f"{p.aspect_ratio.label} {p.notes or ''}"
                ).lower()
                if query not in search_corpus:
                    continue

            results.append(p)

        return sorted(results, key=lambda p: (p.category, p.manufacturer, p.model))

    # --- Favorites & Recents ---

    def _load_favorites_and_recents(self) -> None:
        fav_path = self._user_data_dir / "favorites.json"
        if fav_path.exists():
            try:
                with open(fav_path, "r", encoding="utf-8") as f:
                    self._favorites = set(json.load(f))
            except Exception:
                self._favorites = set()

        rec_path = self._user_data_dir / "recents.json"
        if rec_path.exists():
            try:
                with open(rec_path, "r", encoding="utf-8") as f:
                    self._recents = json.load(f)
            except Exception:
                self._recents = []

    def _save_favorites(self) -> None:
        fav_path = self._user_data_dir / "favorites.json"
        try:
            with open(fav_path, "w", encoding="utf-8") as f:
                json.dump(list(self._favorites), f, indent=2)
        except Exception as e:
            logger.error("Failed to save favorites: %s", e)

    def _save_recents(self) -> None:
        rec_path = self._user_data_dir / "recents.json"
        try:
            with open(rec_path, "w", encoding="utf-8") as f:
                json.dump(self._recents[:20], f, indent=2)
        except Exception as e:
            logger.error("Failed to save recents: %s", e)

    def is_favorite(self, profile_id: str) -> bool:
        return profile_id in self._favorites

    def toggle_favorite(self, profile_id: str) -> bool:
        """Toggle favorite state and return new state."""
        if profile_id in self._favorites:
            self._favorites.remove(profile_id)
            fav = False
        else:
            self._favorites.add(profile_id)
            fav = True
        self._save_favorites()
        self.favorites_changed.emit()
        return fav

    def get_favorite_profiles(self) -> List[ScreenProfile]:
        return [self._profiles[pid] for pid in self._favorites if pid in self._profiles]

    def add_recent(self, profile_id: str) -> None:
        """Track recently accessed profile."""
        if profile_id in self._recents:
            self._recents.remove(profile_id)
        self._recents.insert(0, profile_id)
        self._recents = self._recents[:20]
        self._save_recents()

    def get_recent_profiles(self) -> List[ScreenProfile]:
        return [self._profiles[pid] for pid in self._recents if pid in self._profiles]

    # --- Custom Profiles Management ---

    def save_custom_profile(self, profile: ScreenProfile) -> None:
        """Persist a custom profile to disk and register in manager."""
        profile.category = "custom"
        profile.profile_source = "custom"
        profile.validate()

        file_name = f"{profile.id}.json"
        save_path = self._custom_dir / file_name
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2)

        self._profiles[profile.id] = profile
        self.profile_added.emit(profile)
        logger.info("Saved custom profile: %s to %s", profile.id, save_path)

    def delete_custom_profile(self, profile_id: str) -> bool:
        """Delete a custom profile file and unregister."""
        profile = self._profiles.get(profile_id)
        if not profile or profile.profile_source != "custom":
            return False

        file_name = f"{profile_id}.json"
        save_path = self._custom_dir / file_name
        if save_path.exists():
            try:
                save_path.unlink()
            except Exception as e:
                logger.error("Failed to remove profile file %s: %s", save_path, e)
                return False

        if profile_id in self._profiles:
            del self._profiles[profile_id]

        if profile_id in self._favorites:
            self._favorites.remove(profile_id)
            self._save_favorites()

        self.profile_deleted.emit(profile_id)
        return True

    def import_profile_from_file(self, filepath: str) -> ScreenProfile:
        """Import a JSON profile file, validate, and store."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Import file must contain a single JSON object representing a profile.")

        # Ensure unique ID if imported has duplicate
        p = ScreenProfile.from_dict(data)
        if p.id in self._profiles:
            p.id = f"{p.id}_imported"

        self.save_custom_profile(p)
        return p

    def export_profile_to_file(self, profile_id: str, filepath: str) -> None:
        """Export a profile to a destination JSON file."""
        profile = self.get_profile_by_id(profile_id)
        if not profile:
            raise ValueError(f"Profile '{profile_id}' not found.")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2)
