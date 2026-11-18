"""Aspect ratio and display resolution controls for SUSCRCPY 2.1.

Provides ratio presets, custom pixel inputs, GCD aspect ratio computation,
validation, and resolution reset.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from core.screen_manager import ASPECT_RATIOS, RESOLUTION_NOTICE, ScreenManager

logger = logging.getLogger("suscrcpy.ui.ratio_panel")


class RatioPanel(QtWidgets.QWidget):
    """Controls Android logical display resolution and aspect ratios."""

    apply_requested = QtCore.Signal(int, int)  # width, height
    reset_requested = QtCore.Signal()
    open_library_requested = QtCore.Signal()

    def __init__(
        self,
        screen_manager: ScreenManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.screen_mgr = screen_manager
        self._current_w = 1080
        self._current_h = 1920
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Ratio Group
        group = QtWidgets.QGroupBox("Display Ratio & Resolution Override")
        g_layout = QtWidgets.QVBoxLayout(group)
        g_layout.setSpacing(10)

        # Preset Dropdown
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel("Aspect Ratio Preset:"))
        self.ratio_combo = QtWidgets.QComboBox()
        self.ratio_combo.addItem("Custom (pixels)")
        for preset in ASPECT_RATIOS.keys():
            self.ratio_combo.addItem(preset)
        self.ratio_combo.currentTextChanged.connect(self._on_preset_changed)
        row1.addWidget(self.ratio_combo, stretch=1)
        g_layout.addLayout(row1)

        # Pixel Inputs
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QtWidgets.QLabel("Width (pixels):"), 0, 0)
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setValue(self._current_w)
        self.width_spin.valueChanged.connect(self._recalc_gcd_ratio)
        grid.addWidget(self.width_spin, 0, 1)

        grid.addWidget(QtWidgets.QLabel("Height (pixels):"), 1, 0)
        self.height_spin = QtWidgets.QSpinBox()
        self.height_spin.setRange(100, 10000)
        self.height_spin.setValue(self._current_h)
        self.height_spin.valueChanged.connect(self._recalc_gcd_ratio)
        grid.addWidget(self.height_spin, 1, 1)

        g_layout.addLayout(grid)

        # Live GCD Aspect Ratio Calculation Label
        self.gcd_label = QtWidgets.QLabel("Computed Aspect Ratio: 9:16 (via GCD)")
        self.gcd_label.setStyleSheet("color: #58a6ff; font-weight: 600; font-size: 12px;")
        g_layout.addWidget(self.gcd_label)

        # Action Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(8)

        self.apply_btn = QtWidgets.QPushButton("Apply Resolution")
        self.apply_btn.setObjectName("primaryButton")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        btn_layout.addWidget(self.apply_btn)

        self.reset_btn = QtWidgets.QPushButton("Reset Resolution")
        self.reset_btn.setToolTip("Restore Android native physical resolution (wm size reset)")
        self.reset_btn.clicked.connect(self.reset_requested)
        btn_layout.addWidget(self.reset_btn)

        g_layout.addLayout(btn_layout)

        # Library shortcut button
        self.lib_btn = QtWidgets.QPushButton("📚 Browse Universal Screen Profiles (12 Categories)")
        self.lib_btn.setToolTip("Browse phones, tablets, foldables, smartwatches, monitors, TVs, and XR profiles")
        self.lib_btn.clicked.connect(self.open_library_requested)
        g_layout.addWidget(self.lib_btn)

        # Explanatory Notice
        notice_label = QtWidgets.QLabel(RESOLUTION_NOTICE)
        notice_label.setStyleSheet("color: #8b949e; font-size: 11px; line-height: 1.3;")
        notice_label.setWordWrap(True)
        g_layout.addWidget(notice_label)

        layout.addWidget(group)
        layout.addStretch()

        self._recalc_gcd_ratio()

    def _recalc_gcd_ratio(self) -> None:
        w = self.width_spin.value()
        h = self.height_spin.value()
        rw, rh = ScreenManager.calculate_aspect_ratio(w, h)
        self.gcd_label.setText(f"Computed Aspect Ratio: {rw}:{rh} (via GCD)")

    def set_current_dimensions(self, width: int, height: int) -> None:
        """Update displayed pixel inputs with current device dimensions."""
        self._current_w = width
        self._current_h = height
        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)
        self._recalc_gcd_ratio()

    def _on_preset_changed(self, preset_name: str) -> None:
        if preset_name == "Custom (pixels)":
            return

        try:
            cur_w = self.width_spin.value()
            cur_h = self.height_spin.value()
            new_w, new_h = self.screen_mgr.calculate_dimensions_for_ratio(cur_w, cur_h, preset_name)
            self.width_spin.setValue(new_w)
            self.height_spin.setValue(new_h)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Preset Calculation Error", str(e))

    def _on_apply_clicked(self) -> None:
        w = self.width_spin.value()
        h = self.height_spin.value()
        try:
            w, h = self.screen_mgr.validate_pixels(w, h)
            self.apply_requested.emit(w, h)
        except ValueError as e:
            QtWidgets.QMessageBox.critical(self, "Invalid Dimensions", str(e))
