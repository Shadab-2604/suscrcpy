"""Slim horizontal header bar for SUSCRCPY.

Contains application brand identity, connected device dropdown,
live connection status indicator, and refresh action.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.adb_manager import DeviceItem
from core.device_manager import ConnectionState, DeviceManager
from ui.styles import COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING
from version import APP_NAME, APP_VERSION


class HeaderBar(QtWidgets.QFrame):
    """Header bar positioned across the top of the main window."""

    device_selected = QtCore.Signal(str)  # serial
    refresh_requested = QtCore.Signal()
    check_updates_requested = QtCore.Signal()
    reset_layout_requested = QtCore.Signal()

    def __init__(self, device_manager: DeviceManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")
        self.device_mgr = device_manager
        self._block_signals = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        # Left: Brand Identity
        brand_layout = QtWidgets.QHBoxLayout()
        brand_layout.setSpacing(6)
        self.brand_title = QtWidgets.QLabel(APP_NAME)
        self.brand_title.setObjectName("brandTitle")
        brand_layout.addWidget(self.brand_title)

        version_label = QtWidgets.QLabel(f"v{APP_VERSION}")
        version_label.setStyleSheet("color: #666666; font-size: 11px;")
        brand_layout.addWidget(version_label)
        layout.addLayout(brand_layout)

        layout.addStretch(1)

        # Center: Connected Device Dropdown
        center_layout = QtWidgets.QHBoxLayout()
        center_layout.setSpacing(6)
        center_layout.addWidget(QtWidgets.QLabel("Device:"))

        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setMinimumWidth(260)
        self.device_combo.setMaximumWidth(360)
        self.device_combo.currentIndexChanged.connect(self._on_combo_changed)
        center_layout.addWidget(self.device_combo)
        layout.addLayout(center_layout)

        layout.addStretch(1)

        # Right: Connection Status & Refresh Action & Updates
        right_layout = QtWidgets.QHBoxLayout()
        right_layout.setSpacing(8)

        self.status_dot = QtWidgets.QLabel("● Disconnected")
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setStyleSheet(f"color: {COLOR_ERROR};")
        right_layout.addWidget(self.status_dot)

        self.refresh_btn = QtWidgets.QPushButton("↻ Refresh")
        self.refresh_btn.setToolTip("Scan for connected ADB devices")
        self.refresh_btn.clicked.connect(self.refresh_requested)
        right_layout.addWidget(self.refresh_btn)

        self.layout_btn = QtWidgets.QPushButton("⊞ Reset Layout")
        self.layout_btn.setToolTip("Reset screen and settings splitters to 50/50 division")
        self.layout_btn.clicked.connect(self.reset_layout_requested)
        right_layout.addWidget(self.layout_btn)

        self.updates_btn = QtWidgets.QPushButton("🔄 Updates")
        self.updates_btn.setToolTip("Check for software updates on GitHub")
        self.updates_btn.clicked.connect(self.check_updates_requested)
        right_layout.addWidget(self.updates_btn)

        layout.addLayout(right_layout)

    def _connect_signals(self) -> None:
        self.device_mgr.devices_updated.connect(self.update_devices_list)
        self.device_mgr.status_changed.connect(self.update_status)

    def update_devices_list(self, devices: List[DeviceItem]) -> None:
        """Populate the target device combobox."""
        self._block_signals = True
        current_serial = self.device_mgr.selected_serial
        self.device_combo.clear()

        if not devices:
            self.device_combo.addItem("No Android devices connected", "")
            self.device_combo.setEnabled(False)
            self._block_signals = False
            self.update_status("", ConnectionState.DISCONNECTED.value)
            return

        self.device_combo.setEnabled(True)
        selected_idx = 0
        for idx, dev in enumerate(devices):
            status_tag = "" if dev.is_authorized else f" [{dev.status}]"
            label = f"{dev.model} ({dev.serial}){status_tag}"
            self.device_combo.addItem(label, dev.serial)
            if dev.serial == current_serial:
                selected_idx = idx

        self.device_combo.setCurrentIndex(selected_idx)
        self._block_signals = False

    def _on_combo_changed(self, index: int) -> None:
        if self._block_signals or index < 0:
            return
        serial = self.device_combo.itemData(index)
        if serial:
            self.device_selected.emit(serial)

    def update_status(self, serial: str, state_str: str) -> None:
        """Update live status indicator."""
        if state_str == ConnectionState.CONNECTED.value:
            color = COLOR_SUCCESS
            text = f"● Connected"
        elif state_str in (ConnectionState.UNAUTHORIZED.value, ConnectionState.RECONNECTING.value):
            color = COLOR_WARNING
            text = f"● {state_str}"
        else:
            color = COLOR_ERROR
            text = f"● {state_str}"

        self.status_dot.setText(text)
        self.status_dot.setStyleSheet(f"color: {color}; font-weight: 600;")
