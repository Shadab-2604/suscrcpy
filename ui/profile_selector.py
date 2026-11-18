"""Hierarchical and searchable Universal Screen Profile Selector for SUSCRCPY 2.1."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.profile_manager import ProfileManager
from core.profile_model import CATEGORY_LABELS, ScreenProfile, VALID_CATEGORIES, WIDTH_SIZE_CLASSES
from ui.styles import COLOR_ACCENT, COLOR_BORDER, COLOR_CARD, COLOR_SUCCESS, COLOR_WARNING

logger = logging.getLogger("suscrcpy.ui.profile_selector")


class ProfileSelector(QtWidgets.QWidget):
    """Hierarchical and searchable screen profile browser with favorites and recents."""

    profile_selected = QtCore.Signal(object)  # ScreenProfile
    apply_to_device_requested = QtCore.Signal(object)  # ScreenProfile
    preview_requested = QtCore.Signal(object)  # ScreenProfile

    def __init__(self, profile_manager: ProfileManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.profile_mgr = profile_manager
        self._current_profile: Optional[ScreenProfile] = None
        self._build_ui()
        self._connect_signals()
        self.refresh_tree()

    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. Search Bar & Filter Controls
        search_box = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search by model, brand, resolution (e.g. 1080x2400), aspect ratio...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_box.addWidget(self.search_input)

        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItem("All Categories", "")
        for cat in VALID_CATEGORIES:
            self.category_combo.addItem(CATEGORY_LABELS.get(cat, cat.title()), cat)
        self.category_combo.currentIndexChanged.connect(self._on_filter_changed)
        search_box.addWidget(self.category_combo)

        self.size_class_combo = QtWidgets.QComboBox()
        self.size_class_combo.addItem("All Size Classes", "")
        for _, _, label in WIDTH_SIZE_CLASSES:
            self.size_class_combo.addItem(label, label)
        self.size_class_combo.currentIndexChanged.connect(self._on_filter_changed)
        search_box.addWidget(self.size_class_combo)

        main_layout.addLayout(search_box)

        # Profile Management Tools Bar
        tools_row = QtWidgets.QHBoxLayout()
        tools_row.setSpacing(6)

        self.new_profile_btn = QtWidgets.QPushButton("➕ New Profile")
        self.new_profile_btn.setToolTip("Create a custom screen profile with live GCD aspect ratio calculation")
        self.new_profile_btn.clicked.connect(self._create_custom_profile)
        tools_row.addWidget(self.new_profile_btn)

        self.import_btn = QtWidgets.QPushButton("📥 Import JSON")
        self.import_btn.setToolTip("Import a screen profile from a JSON file")
        self.import_btn.clicked.connect(self._import_profile)
        tools_row.addWidget(self.import_btn)

        self.export_btn = QtWidgets.QPushButton("📤 Export JSON")
        self.export_btn.setToolTip("Export the selected profile to a JSON file")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_profile)
        tools_row.addWidget(self.export_btn)

        self.delete_btn = QtWidgets.QPushButton("🗑 Delete Custom")
        self.delete_btn.setObjectName("dangerButton")
        self.delete_btn.setToolTip("Delete this custom profile")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_custom_profile)
        tools_row.addWidget(self.delete_btn)

        tools_row.addStretch()
        main_layout.addLayout(tools_row)

        # 2. Main Tabs (All Profiles / Favorites / Recents)
        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: All Profiles Hierarchical Tree
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Screen Profile Hierarchy", "Resolution", "Ratio", "Class"])
        self.tree.setColumnWidth(0, 240)
        self.tree.setColumnWidth(1, 110)
        self.tree.setColumnWidth(2, 70)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.tabs.addTab(self.tree, "📚 Universal Library")

        # Tab 2: Favorites List
        self.fav_list = QtWidgets.QListWidget()
        self.fav_list.itemSelectionChanged.connect(self._on_list_selection_changed)
        self.tabs.addTab(self.fav_list, "⭐ Favorites")

        # Tab 3: Recent Profiles List
        self.rec_list = QtWidgets.QListWidget()
        self.rec_list.itemSelectionChanged.connect(self._on_list_selection_changed)
        self.tabs.addTab(self.rec_list, "⏱ Recents")

        main_layout.addWidget(self.tabs, stretch=2)

        # 3. Profile Details Card
        self.details_box = QtWidgets.QGroupBox("Selected Screen Profile Details")
        det_layout = QtWidgets.QVBoxLayout(self.details_box)
        det_layout.setContentsMargins(10, 8, 10, 8)
        det_layout.setSpacing(6)

        self.lbl_title = QtWidgets.QLabel("No profile selected")
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #58a6ff;")
        det_layout.addWidget(self.lbl_title)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)

        self.lbl_specs = QtWidgets.QLabel("Resolution: —")
        self.lbl_ratio = QtWidgets.QLabel("Aspect Ratio: —")
        self.lbl_density = QtWidgets.QLabel("Density: —")
        self.lbl_viewport = QtWidgets.QLabel("Logical Viewport: —")
        self.lbl_class = QtWidgets.QLabel("Window Size Class: —")
        self.lbl_source = QtWidgets.QLabel("Profile Source: —")
        self.lbl_special = QtWidgets.QLabel("Hardware Features: —")
        self.lbl_safe = QtWidgets.QLabel("Safe Area Insets: —")

        grid.addWidget(self.lbl_specs, 0, 0)
        grid.addWidget(self.lbl_ratio, 0, 1)
        grid.addWidget(self.lbl_density, 1, 0)
        grid.addWidget(self.lbl_viewport, 1, 1)
        grid.addWidget(self.lbl_class, 2, 0)
        grid.addWidget(self.lbl_source, 2, 1)
        grid.addWidget(self.lbl_special, 3, 0)
        grid.addWidget(self.lbl_safe, 3, 1)

        det_layout.addLayout(grid)

        # Action Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)

        self.fav_btn = QtWidgets.QPushButton("⭐ Favorite")
        self.fav_btn.setEnabled(False)
        self.fav_btn.clicked.connect(self._toggle_favorite)
        btn_row.addWidget(self.fav_btn)

        self.preview_btn = QtWidgets.QPushButton("📐 Preview Layout (Mode 2)")
        self.preview_btn.setObjectName("primaryButton")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._on_preview_clicked)
        btn_row.addWidget(self.preview_btn)

        self.apply_btn = QtWidgets.QPushButton("📱 Apply to Device (Mode 1)")
        self.apply_btn.setObjectName("successButton")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        btn_row.addWidget(self.apply_btn)

        det_layout.addLayout(btn_row)
        main_layout.addWidget(self.details_box, stretch=1)

    def _connect_signals(self) -> None:
        self.profile_mgr.profiles_loaded.connect(lambda: self.refresh_tree())
        self.profile_mgr.favorites_changed.connect(self._refresh_favorites_and_recents)

    def refresh_tree(self) -> None:
        """Populate hierarchical tree based on current search & category filters."""
        query = self.search_input.text()
        category = self.category_combo.currentData() or None
        size_class = self.size_class_combo.currentData() or None

        self.tree.clear()
        profiles = self.profile_mgr.search_profiles(query=query, category=category, size_class=size_class)

        # Build nested tree: Category -> Platform -> Manufacturer -> Model -> Profile
        categories: Dict[str, Dict[str, Dict[str, Dict[str, List[ScreenProfile]]]]] = {}
        for p in profiles:
            c_label = CATEGORY_LABELS.get(p.category, p.category.title())
            plat = p.platform.title()
            mfg = p.manufacturer or "Generic"
            model = p.model

            categories.setdefault(c_label, {}).setdefault(plat, {}).setdefault(mfg, {}).setdefault(model, []).append(p)

        for c_label, plats in sorted(categories.items()):
            c_item = QtWidgets.QTreeWidgetItem(self.tree, [c_label])
            c_item.setExpanded(True if query else False)

            for plat, mfgs in sorted(plats.items()):
                plat_item = QtWidgets.QTreeWidgetItem(c_item, [plat])
                if query:
                    plat_item.setExpanded(True)

                for mfg, models in sorted(mfgs.items()):
                    mfg_item = QtWidgets.QTreeWidgetItem(plat_item, [mfg])
                    if query:
                        mfg_item.setExpanded(True)

                    for model, p_list in sorted(models.items()):
                        model_item = QtWidgets.QTreeWidgetItem(mfg_item, [model])
                        if query:
                            model_item.setExpanded(True)

                        for p in p_list:
                            w_class, _ = p.get_window_size_classes()
                            res_str = f"{p.resolution.width_px}×{p.resolution.height_px}"
                            p_item = QtWidgets.QTreeWidgetItem(
                                model_item,
                                [p.screen_name, res_str, p.aspect_ratio.label, w_class.split()[0]],
                            )
                            p_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, p)

        self._refresh_favorites_and_recents()

    def _refresh_favorites_and_recents(self) -> None:
        # Favorites
        self.fav_list.clear()
        for p in self.profile_mgr.get_favorite_profiles():
            item = QtWidgets.QListWidgetItem(f"⭐ {p.manufacturer} {p.model} — {p.screen_name} ({p.resolution.width_px}×{p.resolution.height_px})")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, p)
            self.fav_list.addItem(item)

        # Recents
        self.rec_list.clear()
        for p in self.profile_mgr.get_recent_profiles():
            item = QtWidgets.QListWidgetItem(f"⏱ {p.manufacturer} {p.model} — {p.screen_name} ({p.resolution.width_px}×{p.resolution.height_px})")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, p)
            self.rec_list.addItem(item)

    def _on_search_changed(self) -> None:
        self.refresh_tree()

    def _on_filter_changed(self) -> None:
        self.refresh_tree()

    def _on_tree_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        p: Optional[ScreenProfile] = items[0].data(0, QtCore.Qt.ItemDataRole.UserRole)
        if p:
            self._select_profile(p)

    def _on_list_selection_changed(self) -> None:
        sender = self.sender()
        if not isinstance(sender, QtWidgets.QListWidget):
            return
        items = sender.selectedItems()
        if not items:
            return
        p = items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        if p:
            self._select_profile(p)

    def _select_profile(self, p: ScreenProfile) -> None:
        self._current_profile = p
        self.profile_mgr.add_recent(p.id)
        self.profile_selected.emit(p)

        # Populate Details
        verified_badge = " [Verified Specification]" if p.verified else " [Generic Representative]"
        self.lbl_title.setText(f"{p.manufacturer} {p.model} — {p.screen_name}{verified_badge}")
        self.lbl_specs.setText(f"Resolution: {p.resolution.width_px} × {p.resolution.height_px} px ({p.orientation})")
        self.lbl_ratio.setText(f"Aspect Ratio: {p.aspect_ratio.label}")

        dpi_str = f"{p.density.dpi} DPI" if p.density.dpi else "Standard"
        scale_str = f"{p.density.scale_factor}x" if p.density.scale_factor else "1.0x"
        self.lbl_density.setText(f"Density: {dpi_str} (Scale {scale_str})")

        vp_w = p.logical_viewport.width_dp or "Auto"
        vp_h = p.logical_viewport.height_dp or "Auto"
        self.lbl_viewport.setText(f"Logical Viewport: {vp_w} × {vp_h} dp")

        w_class, h_class = p.get_window_size_classes()
        self.lbl_class.setText(f"Window Size Class: {w_class}")
        self.lbl_source.setText(f"Platform: {p.platform.title()} | Category: {p.category.title()}")

        features = []
        if p.shape != "rectangle":
            features.append(f"Shape: {p.shape.title()}")
        if p.cutouts:
            features.append(f"{len(p.cutouts)} Cutout(s) [{p.cutouts[0].type}]")
        if p.foldable.enabled:
            features.append(f"Foldable ({p.foldable.display_mode or 'inner'} mode)")
        if p.xr.enabled:
            features.append(f"XR Stereo ({p.xr.fov_deg}° FOV, {p.xr.per_eye_width_px}x{p.xr.per_eye_height_px}/eye)")
        if p.dual_screen.enabled:
            features.append("Dual-Monitor Canvas")
        if p.refresh_rate_hz:
            features.append(f"{p.refresh_rate_hz} Hz")

        self.lbl_special.setText(f"Features: {', '.join(features) if features else 'Standard Display'}")
        self.lbl_safe.setText(f"Safe Insets: T:{p.safe_areas.top} B:{p.safe_areas.bottom} L:{p.safe_areas.left} R:{p.safe_areas.right}")

        # Update button states
        self.preview_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)
        self.fav_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.delete_btn.setEnabled(p.profile_source == "custom")

        is_fav = self.profile_mgr.is_favorite(p.id)
        self.fav_btn.setText("★ Favorited" if is_fav else "☆ Add Favorite")

    def _create_custom_profile(self) -> None:
        from ui.custom_profile_dialog import CustomProfileDialog

        dlg = CustomProfileDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            p = dlg.get_created_profile()
            if p:
                self.profile_mgr.save_custom_profile(p)
                self.refresh_tree()
                self._select_profile(p)
                QtWidgets.QMessageBox.information(self, "Profile Saved", f"Custom profile '{p.model}' created successfully.")

    def _import_profile(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import Screen Profile JSON", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            p = self.profile_mgr.import_profile_from_file(path)
            self.refresh_tree()
            self._select_profile(p)
            QtWidgets.QMessageBox.information(self, "Import Successful", f"Imported profile: {p.manufacturer} {p.model}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", f"Failed to import profile:\n{e}")

    def _export_profile(self) -> None:
        if not self._current_profile:
            return
        p = self._current_profile
        default_name = f"{p.id}.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Screen Profile JSON", default_name, "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            self.profile_mgr.export_profile_to_file(p.id, path)
            QtWidgets.QMessageBox.information(self, "Export Successful", f"Saved profile to:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Failed to export profile:\n{e}")

    def _delete_custom_profile(self) -> None:
        if not self._current_profile or self._current_profile.profile_source != "custom":
            return
        p = self._current_profile
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete Profile",
            f"Are you sure you want to delete custom profile '{p.model}' ({p.id})?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.profile_mgr.delete_custom_profile(p.id)
            self.refresh_tree()
            self.lbl_title.setText("Profile deleted")
            self.preview_btn.setEnabled(False)
            self.apply_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self.export_btn.setEnabled(False)

    def _toggle_favorite(self) -> None:
        if not self._current_profile:
            return
        is_fav = self.profile_mgr.toggle_favorite(self._current_profile.id)
        self.fav_btn.setText("★ Favorited" if is_fav else "☆ Add Favorite")

    def _on_preview_clicked(self) -> None:
        if self._current_profile:
            self.preview_requested.emit(self._current_profile)

    def _on_apply_clicked(self) -> None:
        if not self._current_profile:
            return

        # Section J compliance: strictly distinguish ADB controllable devices
        p = self._current_profile
        if p.category in ("laptop", "monitor", "xr") or p.platform in ("windows", "macos", "ios", "ipados", "visionos"):
            reply = QtWidgets.QMessageBox.warning(
                self,
                "Device Compatibility Notice",
                f"The selected profile '{p.model}' is a {p.platform.title()} / {p.category.title()} screen profile.\n\n"
                "Android Debug Bridge ('wm size') commands can only be applied to connected Android devices. "
                "Applying this resolution will override your connected Android device's logical display dimensions to simulate this screen.\n\n"
                "Do you want to apply this resolution to your connected Android device?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return

        self.apply_to_device_requested.emit(p)
