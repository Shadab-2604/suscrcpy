"""Display resolution and aspect-ratio controls for SUSCRCPY."""
from __future__ import annotations

from typing import Optional, Tuple

from PySide6 import QtCore, QtWidgets

from core.screen_manager import ASPECT_RATIOS, PRESET_ORDER, RESOLUTION_NOTICE, ScreenManager


class DisplayPanel(QtWidgets.QWidget):
    """Apply a logical resolution/ratio override and reset it again."""

    apply_requested = QtCore.Signal(int, int)
    reset_requested = QtCore.Signal()

    def __init__(
        self,
        screen_manager: ScreenManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.screen_mgr = screen_manager
        self._syncing = False
        self._build_ui()

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Current device state
        self.current_lbl = QtWidgets.QLabel("No device connected")
        self.current_lbl.setObjectName("stateLabel")
        layout.addWidget(self.current_lbl)

        # Ratio preset
        ratio_row = QtWidgets.QHBoxLayout()
        ratio_row.setSpacing(8)
        ratio_row.addWidget(QtWidgets.QLabel("Aspect ratio"))

        self.ratio_combo = QtWidgets.QComboBox()
        self.ratio_combo.addItem("Custom")
        for preset in PRESET_ORDER:
            self.ratio_combo.addItem(preset)
        self.ratio_combo.currentTextChanged.connect(self._on_preset_changed)
        ratio_row.addWidget(self.ratio_combo, stretch=1)
        layout.addLayout(ratio_row)

        # Pixel inputs
        size_row = QtWidgets.QHBoxLayout()
        size_row.setSpacing(8)
        size_row.addWidget(QtWidgets.QLabel("Width"))
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(100, 10000)
        self.width_spin.setSingleStep(10)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        size_row.addWidget(self.width_spin)

        size_row.addWidget(QtWidgets.QLabel("Height"))
        self.height_spin = QtWidgets.QSpinBox()
        self.height_spin.setRange(100, 10000)
        self.height_spin.setSingleStep(10)
        self.height_spin.valueChanged.connect(self._on_height_changed)
        size_row.addWidget(self.height_spin)
        layout.addLayout(size_row)

        # Exact ratio of the current input
        self.ratio_lbl = QtWidgets.QLabel("Ratio: --")
        self.ratio_lbl.setObjectName("ratioLabel")
        layout.addWidget(self.ratio_lbl)

        # Actions
        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(8)
        self.apply_btn = QtWidgets.QPushButton("Apply resolution")
        self.apply_btn.setObjectName("primaryBtn")
        self.apply_btn.setToolTip("Apply this logical resolution to the device (wm size)")
        self.apply_btn.clicked.connect(self._on_apply)
        button_row.addWidget(self.apply_btn)

        self.reset_btn = QtWidgets.QPushButton("Reset")
        self.reset_btn.setToolTip("Restore the device's native resolution")
        self.reset_btn.clicked.connect(self.reset_requested)
        button_row.addWidget(self.reset_btn)
        layout.addLayout(button_row)

        notice = QtWidgets.QLabel(RESOLUTION_NOTICE)
        notice.setObjectName("noticeLabel")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        layout.addStretch(1)

    # -------------------------------------------------------------- state
    def set_current_dimensions(self, width: int, height: int, is_override: bool = False) -> None:
        self._syncing = True
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        self._syncing = False
        self._refresh_ratio_label()
        state = "override active" if is_override else "native"
        self.current_lbl.setText(f"Current: {width} \u00d7 {height} px ({state})")
        self.apply_btn.setEnabled(True)
        self.reset_btn.setEnabled(is_override)

    def clear_device(self) -> None:
        self.current_lbl.setText("No device connected")
        self.ratio_combo.setCurrentText("Custom")
        self.apply_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)

    def set_device_ready(self) -> None:
        self.apply_btn.setEnabled(True)

    # ------------------------------------------------------------- ratios
    def _refresh_ratio_label(self) -> None:
        width = self.width_spin.value()
        height = self.height_spin.value()
        label = ScreenManager.ratio_label(width, height)
        orientation = "portrait" if height >= width else "landscape"
        self.ratio_lbl.setText(f"Ratio: {label} ({orientation})")

    def _on_preset_changed(self, preset: str) -> None:
        if self._syncing or preset not in ASPECT_RATIOS:
            return
        try:
            new_w, new_h = self.screen_mgr.calculate_dimensions_for_ratio(
                self.width_spin.value(), self.height_spin.value(), preset
            )
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid ratio", str(exc))
            return
        self._apply_inputs(new_w, new_h)

    def _on_width_changed(self, width: int) -> None:
        if self._syncing:
            return
        preset = self.ratio_combo.currentText()
        if preset in ASPECT_RATIOS:
            long_factor, short_factor = ASPECT_RATIOS[preset]
            orientation_portrait = self.height_spin.value() >= width
            if orientation_portrait:
                new_h = int(round(width * long_factor / short_factor))
            else:
                new_h = int(round(width * short_factor / long_factor))
            self._apply_inputs(width, max(100, new_h))
        else:
            self._refresh_ratio_label()

    def _on_height_changed(self, height: int) -> None:
        if self._syncing:
            return
        preset = self.ratio_combo.currentText()
        if preset in ASPECT_RATIOS:
            long_factor, short_factor = ASPECT_RATIOS[preset]
            orientation_portrait = height >= self.width_spin.value()
            if orientation_portrait:
                new_w = int(round(height * short_factor / long_factor))
            else:
                new_w = int(round(height * long_factor / short_factor))
            self._apply_inputs(max(100, new_w), height)
        else:
            self._refresh_ratio_label()

    def _apply_inputs(self, width: int, height: int) -> None:
        self._syncing = True
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        self._syncing = False
        self._refresh_ratio_label()

    def _on_apply(self) -> None:
        try:
            width, height = self.screen_mgr.validate_pixels(
                self.width_spin.value(), self.height_spin.value()
            )
        except ValueError as exc:
            QtWidgets.QMessageBox.critical(self, "Invalid dimensions", str(exc))
            return
        self.apply_requested.emit(width, height)
