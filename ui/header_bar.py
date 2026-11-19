"""Slim top bar: brand, device selector, connection state, refresh."""
from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from core.adb_manager import DeviceItem
from core.device_manager import ConnectionState, DeviceManager
from ui.styles import COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING
from version import APP_NAME, APP_VERSION


class HeaderBar(QtWidgets.QFrame):
    """Connection header for the single-window workstation."""

    device_selected = QtCore.Signal(str)
    refresh_requested = QtCore.Signal()

    def __init__(self, device_manager: DeviceManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")
        self.device_mgr = device_manager
        self._block = False
        self._build_ui()
        self.device_mgr.devices_updated.connect(self.update_devices)
        self.device_mgr.status_changed.connect(self.update_status)

    def _build_ui(self) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(APP_NAME)
        title.setObjectName("brandTitle")
        layout.addWidget(title)

        version = QtWidgets.QLabel(f"v{APP_VERSION}")
        version.setObjectName("brandVersion")
        layout.addWidget(version)

        layout.addStretch(1)

        layout.addWidget(QtWidgets.QLabel("Device"))
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setMinimumWidth(300)
        self.device_combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.device_combo)

        self.status_lbl = QtWidgets.QLabel("\u25cf Disconnected")
        self.status_lbl.setObjectName("statusDot")
        self.status_lbl.setStyleSheet(f"color: {COLOR_ERROR};")
        layout.addWidget(self.status_lbl)

        layout.addStretch(1)

        self.refresh_btn = QtWidgets.QPushButton("Refresh devices")
        self.refresh_btn.setObjectName("ghostBtn")
        self.refresh_btn.setToolTip("Scan for connected ADB devices")
        self.refresh_btn.clicked.connect(self.refresh_requested)
        layout.addWidget(self.refresh_btn)

    # ---------------------------------------------------------------- data
    def update_devices(self, devices: List[DeviceItem]) -> None:
        self._block = True
        self.device_combo.clear()
        selected = self.device_mgr.selected_serial

        if not devices:
            self.device_combo.addItem("No Android devices connected", "")
            self.device_combo.setEnabled(False)
            self._block = False
            self.update_status("", ConnectionState.DISCONNECTED.value)
            return

        self.device_combo.setEnabled(True)
        index = 0
        for position, device in enumerate(devices):
            suffix = "" if device.is_authorized else f"  [{device.status}]"
            self.device_combo.addItem(f"{device.model}  ({device.serial}){suffix}", device.serial)
            if device.serial == selected:
                index = position
        self.device_combo.setCurrentIndex(index)
        self._block = False

    def _on_combo_changed(self, index: int) -> None:
        if self._block or index < 0:
            return
        serial = self.device_combo.itemData(index)
        if serial:
            self.device_selected.emit(serial)

    def update_status(self, serial: str, state: str) -> None:
        if state == ConnectionState.CONNECTED.value:
            color, text = COLOR_SUCCESS, "\u25cf Connected"
        elif state in (ConnectionState.UNAUTHORIZED.value, ConnectionState.RECONNECTING.value,
                       ConnectionState.CONNECTING.value):
            color, text = COLOR_WARNING, f"\u25cf {state}"
        else:
            color, text = COLOR_ERROR, f"\u25cf {state}"
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"color: {color};")
