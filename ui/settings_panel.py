"""Screen and Application Settings panel (Right Upper Panel) for SUSCRCPY.

Houses display resolution / aspect ratio controls and the installed application selector.
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.app_manager import AppInfo, AppManager
from core.screen_manager import ScreenManager

logger = logging.getLogger("suscrcpy.ui.settings_panel")


class SettingsPanel(QtWidgets.QFrame):
    """Right upper panel combining screen ratio/resolution controls and app selection."""

    apply_resolution_requested = QtCore.Signal(int, int)  # width, height
    reset_resolution_requested = QtCore.Signal()
    open_library_requested = QtCore.Signal()
    application_selected = QtCore.Signal(str)  # package_name or "" for all
    refresh_apps_requested = QtCore.Signal()

    def __init__(
        self,
        screen_manager: ScreenManager,
        app_manager: AppManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.screen_mgr = screen_manager
        self.app_mgr = app_manager
        self._all_apps: List[AppInfo] = []
        self._block_signals = False
        self._block_ratio_sync = False

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # ======================================================================
        # Section A: Screen Configuration
        # ======================================================================
        screen_box = QtWidgets.QGroupBox("Screen Configuration")
        s_layout = QtWidgets.QVBoxLayout(screen_box)
        s_layout.setSpacing(8)

        # Row 1: Aspect Ratio Preset & Library Button
        r1 = QtWidgets.QHBoxLayout()
        r1.addWidget(QtWidgets.QLabel("Aspect Ratio:"))
        self.ratio_combo = QtWidgets.QComboBox()
        self.ratio_combo.addItem("Custom (pixels)")
        for preset in ["1:1", "4:3", "5:4", "16:9", "16:10", "18:9", "19.5:9", "20:9"]:
            self.ratio_combo.addItem(preset)
        self.ratio_combo.currentTextChanged.connect(self._on_preset_changed)
        r1.addWidget(self.ratio_combo, stretch=1)

        self.library_btn = QtWidgets.QPushButton("📚 Profiles")
        self.library_btn.setToolTip("Browse Universal Screen Profiles Library")
        self.library_btn.clicked.connect(self.open_library_requested)
        r1.addWidget(self.library_btn)

        s_layout.addLayout(r1)

        # Row 2: Resolution (Width & Height)
        r2 = QtWidgets.QHBoxLayout()
        r2.setSpacing(6)

        r2.addWidget(QtWidgets.QLabel("W:"))
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setValue(1080)
        self.width_spin.setToolTip("Width in pixels (100 - 10000)")
        self.width_spin.valueChanged.connect(self._on_width_changed)
        r2.addWidget(self.width_spin)

        r2.addWidget(QtWidgets.QLabel("H:"))
        self.height_spin = QtWidgets.QSpinBox()
        self.height_spin.setRange(100, 10000)
        self.height_spin.setValue(1920)
        self.height_spin.setToolTip("Height in pixels (100 - 10000)")
        self.height_spin.valueChanged.connect(self._on_height_changed)
        r2.addWidget(self.height_spin)

        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.apply_btn.setObjectName("primaryBtn")
        self.apply_btn.setToolTip("Apply logical display resolution via 'wm size'")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        r2.addWidget(self.apply_btn)

        self.reset_btn = QtWidgets.QPushButton("Reset")
        self.reset_btn.setToolTip("Restore original physical resolution (wm size reset)")
        self.reset_btn.clicked.connect(self.reset_resolution_requested)
        r2.addWidget(self.reset_btn)

        s_layout.addLayout(r2)

        # Row 3: Live Status & GCD Ratio info
        r3 = QtWidgets.QHBoxLayout()
        self.active_res_lbl = QtWidgets.QLabel("Active Resolution: —")
        self.active_res_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        r3.addWidget(self.active_res_lbl)

        r3.addStretch()

        self.gcd_ratio_lbl = QtWidgets.QLabel("Computed: 9:16")
        self.gcd_ratio_lbl.setStyleSheet("color: #4A90E2; font-size: 11px; font-weight: 500;")
        r3.addWidget(self.gcd_ratio_lbl)
        s_layout.addLayout(r3)

        layout.addWidget(screen_box)

        # ======================================================================
        # Section B: Android Application Selector
        # ======================================================================
        app_box = QtWidgets.QGroupBox("Target Application")
        a_layout = QtWidgets.QVBoxLayout(app_box)
        a_layout.setSpacing(6)

        # Search Bar Row
        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(6)

        self.app_search_input = QtWidgets.QLineEdit()
        self.app_search_input.setPlaceholderText("🔍 Search apps by name or package (e.g. settings, chrome)...")
        self.app_search_input.setClearButtonEnabled(True)
        self.app_search_input.textChanged.connect(self._on_app_search_changed)
        self.app_search_input.returnPressed.connect(self._on_search_return_pressed)
        search_row.addWidget(self.app_search_input)

        self.refresh_apps_btn = QtWidgets.QPushButton("↻")
        self.refresh_apps_btn.setMaximumWidth(32)
        self.refresh_apps_btn.setToolTip("Refresh installed packages via ADB")
        self.refresh_apps_btn.clicked.connect(self.refresh_apps_requested)
        search_row.addWidget(self.refresh_apps_btn)

        a_layout.addLayout(search_row)

        # Dropdown Row
        app_row = QtWidgets.QHBoxLayout()
        app_row.setSpacing(6)

        self.app_combo = QtWidgets.QComboBox()
        self.app_combo.addItem("All Applications (Full Device Logs)", "")
        self.app_combo.currentIndexChanged.connect(self._on_app_combo_changed)
        app_row.addWidget(self.app_combo, stretch=1)

        a_layout.addLayout(app_row)

        # Filter categories and selection indicator
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(8)

        self.filter_all = QtWidgets.QRadioButton("All")
        self.filter_all.setChecked(True)
        self.filter_all.toggled.connect(self._on_app_filter_toggled)
        filter_row.addWidget(self.filter_all)

        self.filter_user = QtWidgets.QRadioButton("User Apps")
        self.filter_user.toggled.connect(self._on_app_filter_toggled)
        filter_row.addWidget(self.filter_user)

        self.filter_system = QtWidgets.QRadioButton("System Apps")
        self.filter_system.toggled.connect(self._on_app_filter_toggled)
        filter_row.addWidget(self.filter_system)

        filter_row.addStretch()

        self.selected_pkg_lbl = QtWidgets.QLabel("Logs: Entire Device")
        self.selected_pkg_lbl.setStyleSheet("color: #65B58A; font-weight: 500; font-size: 11px;")
        filter_row.addWidget(self.selected_pkg_lbl)

        a_layout.addLayout(filter_row)
        layout.addWidget(app_box)

    def _connect_signals(self) -> None:
        self.app_mgr.apps_loaded.connect(self.set_applications)

    def set_current_dimensions(self, width: int, height: int, is_override: bool = False) -> None:
        """Update spinboxes and status label from device state."""
        self._block_ratio_sync = True
        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)
        self._block_ratio_sync = False

        self._update_gcd_ratio(width, height)
        tag = "Override" if is_override else "Native"
        self.active_res_lbl.setText(f"Active Resolution: {width} × {height} px ({tag})")

    def _update_gcd_ratio(self, w: int, h: int) -> None:
        if w > 0 and h > 0:
            g = math.gcd(w, h)
            self.gcd_ratio_lbl.setText(f"Computed: {w // g}:{h // g}")

    def _on_preset_changed(self, preset_name: str) -> None:
        if preset_name == "Custom (pixels)" or self._block_ratio_sync:
            return

        try:
            cur_w = self.width_spin.value()
            cur_h = self.height_spin.value()
            new_w, new_h = self.screen_mgr.calculate_dimensions_for_ratio(cur_w, cur_h, preset_name)
            self._block_ratio_sync = True
            self.width_spin.setValue(new_w)
            self.height_spin.setValue(new_h)
            self._block_ratio_sync = False
            self._update_gcd_ratio(new_w, new_h)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Preset Error", str(e))

    def _on_width_changed(self, w: int) -> None:
        if self._block_ratio_sync:
            return

        preset = self.ratio_combo.currentText()
        if preset != "Custom (pixels)" and ":" in preset:
            parts = preset.split(":")
            try:
                rw, rh = float(parts[0]), float(parts[1])
                new_h = int(round(w * (rh / rw)))
                self._block_ratio_sync = True
                self.height_spin.setValue(new_h)
                self._block_ratio_sync = False
            except Exception:
                pass

        self._update_gcd_ratio(self.width_spin.value(), self.height_spin.value())

    def _on_height_changed(self, h: int) -> None:
        if self._block_ratio_sync:
            return

        preset = self.ratio_combo.currentText()
        if preset != "Custom (pixels)" and ":" in preset:
            parts = preset.split(":")
            try:
                rw, rh = float(parts[0]), float(parts[1])
                new_w = int(round(h * (rw / rh)))
                self._block_ratio_sync = True
                self.width_spin.setValue(new_w)
                self._block_ratio_sync = False
            except Exception:
                pass

        self._update_gcd_ratio(self.width_spin.value(), self.height_spin.value())

    def _on_apply_clicked(self) -> None:
        w = self.width_spin.value()
        h = self.height_spin.value()
        try:
            w, h = self.screen_mgr.validate_pixels(w, h)
            self.apply_resolution_requested.emit(w, h)
            self.active_res_lbl.setText(f"Active Resolution: {w} × {h} px (Applied)")
        except ValueError as e:
            QtWidgets.QMessageBox.critical(self, "Invalid Dimensions", str(e))

    def set_applications(self, apps: List[AppInfo]) -> None:
        """Update internal application list and populate combobox."""
        self._all_apps = apps
        self._repopulate_app_combo()

    def _on_app_search_changed(self, text: str) -> None:
        self._repopulate_app_combo()

    def _on_search_return_pressed(self) -> None:
        # If user presses Enter in search bar and matching apps exist, select the first match
        if self.app_combo.count() > 1:
            self.app_combo.setCurrentIndex(1)

    def _on_app_filter_toggled(self) -> None:
        self._repopulate_app_combo()

    def _repopulate_app_combo(self) -> None:
        self._block_signals = True
        self.app_combo.clear()

        category = "all"
        if self.filter_user.isChecked():
            category = "user"
        elif self.filter_system.isChecked():
            category = "system"

        query = self.app_search_input.text().strip() if hasattr(self, "app_search_input") else ""
        filtered = self.app_mgr.filter_apps(self._all_apps, query=query, category=category)

        if query:
            header_text = f"All Applications ({len(filtered)} matches found)"
        else:
            header_text = f"All Applications ({len(filtered)} loaded)"

        self.app_combo.addItem(header_text, "")

        for app in filtered:
            type_tag = "[System]" if app.is_system else "[User]"
            label = f"{app.display_name} ({app.package_name}) {type_tag}"
            self.app_combo.addItem(label, app.package_name)

        self._block_signals = False

    def _on_app_combo_changed(self, index: int) -> None:
        if self._block_signals or index < 0:
            return
        pkg = self.app_combo.itemData(index) or ""
        if pkg:
            self.selected_pkg_lbl.setText(f"Logs: {pkg}")
            self.selected_pkg_lbl.setStyleSheet("color: #4A90E2; font-weight: 500; font-size: 11px;")
        else:
            self.selected_pkg_lbl.setText("Logs: Entire Device")
            self.selected_pkg_lbl.setStyleSheet("color: #65B58A; font-weight: 500; font-size: 11px;")
        self.application_selected.emit(pkg)
