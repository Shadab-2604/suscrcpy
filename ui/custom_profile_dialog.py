"""Dialog for creating and editing custom screen profiles in SUSCRCPY 2.1."""
from __future__ import annotations

import uuid
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.profile_model import (
    AspectRatio,
    CATEGORY_LABELS,
    Cutout,
    Density,
    FoldableInfo,
    LogicalViewport,
    Resolution,
    SafeAreas,
    ScreenProfile,
    VALID_CATEGORIES,
    XRInfo,
)


class CustomProfileDialog(QtWidgets.QDialog):
    """Dialog to create or edit a custom screen profile with live aspect ratio calculation."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Custom Screen Profile")
        self.resize(520, 580)
        self._created_profile: Optional[ScreenProfile] = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        form = QtWidgets.QFormLayout()
        form.setSpacing(8)

        # Category
        self.cat_combo = QtWidgets.QComboBox()
        for c in VALID_CATEGORIES:
            self.cat_combo.addItem(CATEGORY_LABELS.get(c, c.title()), c)
        form.addRow("Device Category:", self.cat_combo)

        # Platform
        self.plat_combo = QtWidgets.QComboBox()
        for p in ["android", "ios", "windows", "macos", "linux", "generic"]:
            self.plat_combo.addItem(p.title(), p)
        form.addRow("Platform:", self.plat_combo)

        # Manufacturer & Model
        self.mfg_input = QtWidgets.QLineEdit("CustomBrand")
        form.addRow("Manufacturer:", self.mfg_input)

        self.model_input = QtWidgets.QLineEdit("Custom Device 1")
        form.addRow("Device Model:", self.model_input)

        self.screen_input = QtWidgets.QLineEdit("Main Display")
        form.addRow("Screen Name:", self.screen_input)

        # Dimensions
        dim_layout = QtWidgets.QHBoxLayout()
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setValue(1080)
        self.width_spin.valueChanged.connect(self._recalc_aspect_ratio)
        dim_layout.addWidget(QtWidgets.QLabel("W:"))
        dim_layout.addWidget(self.width_spin)

        self.height_spin = QtWidgets.QSpinBox()
        self.height_spin.setRange(100, 10000)
        self.height_spin.setValue(2400)
        self.height_spin.valueChanged.connect(self._recalc_aspect_ratio)
        dim_layout.addWidget(QtWidgets.QLabel("H:"))
        dim_layout.addWidget(self.height_spin)

        form.addRow("Resolution (px):", dim_layout)

        # Calculated Aspect Ratio
        self.ratio_label = QtWidgets.QLabel("9:20 (Calculated via GCD)")
        self.ratio_label.setStyleSheet("color: #58a6ff; font-weight: 600;")
        form.addRow("Aspect Ratio:", self.ratio_label)

        # Density
        den_layout = QtWidgets.QHBoxLayout()
        self.dpi_spin = QtWidgets.QSpinBox()
        self.dpi_spin.setRange(50, 1500)
        self.dpi_spin.setValue(400)
        den_layout.addWidget(QtWidgets.QLabel("DPI:"))
        den_layout.addWidget(self.dpi_spin)

        self.scale_spin = QtWidgets.QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 6.0)
        self.scale_spin.setSingleStep(0.25)
        self.scale_spin.setValue(2.5)
        den_layout.addWidget(QtWidgets.QLabel("Scale:"))
        den_layout.addWidget(self.scale_spin)

        form.addRow("Density:", den_layout)

        # Orientation & Shape
        self.orient_combo = QtWidgets.QComboBox()
        self.orient_combo.addItems(["portrait", "landscape"])
        form.addRow("Orientation:", self.orient_combo)

        self.shape_combo = QtWidgets.QComboBox()
        self.shape_combo.addItems(["rectangle", "round", "curved"])
        form.addRow("Shape:", self.shape_combo)

        # Cutout
        self.cutout_combo = QtWidgets.QComboBox()
        self.cutout_combo.addItem("None", "none")
        self.cutout_combo.addItem("Punch Hole Camera", "punch_hole")
        self.cutout_combo.addItem("Display Notch", "notch")
        self.cutout_combo.addItem("Dynamic Island", "dynamic_island")
        form.addRow("Hardware Cutout:", self.cutout_combo)

        # Safe Areas
        sa_layout = QtWidgets.QHBoxLayout()
        self.sa_top = QtWidgets.QSpinBox()
        self.sa_top.setRange(0, 300)
        self.sa_top.setValue(48)
        sa_layout.addWidget(QtWidgets.QLabel("T:"))
        sa_layout.addWidget(self.sa_top)

        self.sa_bot = QtWidgets.QSpinBox()
        self.sa_bot.setRange(0, 300)
        self.sa_bot.setValue(48)
        sa_layout.addWidget(QtWidgets.QLabel("B:"))
        sa_layout.addWidget(self.sa_bot)

        self.sa_side = QtWidgets.QSpinBox()
        self.sa_side.setRange(0, 300)
        self.sa_side.setValue(0)
        sa_layout.addWidget(QtWidgets.QLabel("Sides:"))
        sa_layout.addWidget(self.sa_side)

        form.addRow("Safe Area Insets (px):", sa_layout)

        layout.addLayout(form)
        layout.addStretch()

        # Dialog Buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._recalc_aspect_ratio()

    def _recalc_aspect_ratio(self) -> None:
        w = self.width_spin.value()
        h = self.height_spin.value()
        ar = ScreenProfile.calculate_aspect_ratio(w, h)
        self.ratio_label.setText(f"{ar.width}:{ar.height} (Calculated via GCD)")

    def _on_accept(self) -> None:
        model = self.model_input.text().strip()
        if not model:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Device Model name is required.")
            return

        w = self.width_spin.value()
        h = self.height_spin.value()
        ar = ScreenProfile.calculate_aspect_ratio(w, h)

        clean_id = f"custom-{uuid.uuid4().hex[:8]}"

        cutouts = []
        c_type = self.cutout_combo.currentData()
        if c_type == "punch_hole":
            cutouts.append(Cutout(type="punch_hole", x=w // 2, y=36, width=28, height=28, radius=14))
        elif c_type == "notch":
            cutouts.append(Cutout(type="notch", x=w // 2, y=0, width=120, height=44, radius=8))
        elif c_type == "dynamic_island":
            cutouts.append(Cutout(type="dynamic_island", x=w // 2, y=42, width=125, height=37, radius=18))

        scale = self.scale_spin.value()
        self._created_profile = ScreenProfile(
            id=clean_id,
            category=self.cat_combo.currentData(),
            platform=self.plat_combo.currentData(),
            manufacturer=self.mfg_input.text().strip() or "Custom",
            model=model,
            screen_name=self.screen_input.text().strip() or "Main Display",
            resolution=Resolution(width_px=w, height_px=h),
            aspect_ratio=ar,
            density=Density(dpi=self.dpi_spin.value(), scale_factor=scale),
            logical_viewport=LogicalViewport(width_dp=round(w / scale), height_dp=round(h / scale)),
            orientation=self.orient_combo.currentText(),
            shape=self.shape_combo.currentText(),
            cutouts=cutouts,
            safe_areas=SafeAreas(
                top=self.sa_top.value(),
                bottom=self.sa_bot.value(),
                left=self.sa_side.value(),
                right=self.sa_side.value(),
            ),
            profile_source="custom",
            verified=False,
        )
        self.accept()

    def get_created_profile(self) -> Optional[ScreenProfile]:
        return self._created_profile
