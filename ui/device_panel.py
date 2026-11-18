"""Device management panel for SUSCRCPY.

Provides device selection, connection status badges, hardware and system diagnostics,
and manual refresh / reconnect actions.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.adb_manager import DeviceDetails, DeviceItem
from core.device_manager import ConnectionState, DeviceManager
from ui.styles import COLOR_ACCENT, COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING

logger = logging.getLogger("suscrcpy.ui.device_panel")


class DevicePanel(QtWidgets.QWidget):
    """Controls connected device selection and displays hardware diagnostics."""

    device_selected = QtCore.Signal(str)  # serial
    refresh_requested = QtCore.Signal()
    reconnect_requested = QtCore.Signal()

    def __init__(self, device_manager: DeviceManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.device_mgr = device_manager
        self._block_signals = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # Top Control Row
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(10)

        # Brand
        brand = QtWidgets.QLabel("SUSCRCPY 2.0")
        brand.setObjectName("brandLabel")
        top_row.addWidget(brand)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        sep.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        top_row.addWidget(sep)

        # Device Combobox
        dev_label = QtWidgets.QLabel("Target Device:")
        dev_label.setStyleSheet("font-weight: 600;")
        top_row.addWidget(dev_label)

        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setMinimumWidth(260)
        self.device_combo.currentIndexChanged.connect(self._on_combo_changed)
        top_row.addWidget(self.device_combo)

        # Status Badge
        self.status_badge = QtWidgets.QLabel("Disconnected")
        self.status_badge.setObjectName("statusBadgeError")
        top_row.addWidget(self.status_badge)

        # Refresh Button
        self.refresh_btn = QtWidgets.QPushButton("↻ Refresh")
        self.refresh_btn.setToolTip("Scan for connected ADB devices")
        self.refresh_btn.clicked.connect(self.refresh_requested)
        top_row.addWidget(self.refresh_btn)

        # Reconnect Button
        self.reconnect_btn = QtWidgets.QPushButton("⚡ Reconnect")
        self.reconnect_btn.setToolTip("Restart ADB server and re-probe active connection")
        self.reconnect_btn.clicked.connect(self.reconnect_requested)
        top_row.addWidget(self.reconnect_btn)

        top_row.addStretch()
        main_layout.addLayout(top_row)

        # Collapsible Device Info Bar
        self.info_box = QtWidgets.QGroupBox("Device Hardware & System Diagnostics")
        info_layout = QtWidgets.QGridLayout(self.info_box)
        info_layout.setContentsMargins(10, 8, 10, 8)
        info_layout.setHorizontalSpacing(18)
        info_layout.setVerticalSpacing(4)

        # Labels
        self.lbl_model = QtWidgets.QLabel("Model: —")
        self.lbl_os = QtWidgets.QLabel("Android OS: —")
        self.lbl_arch = QtWidgets.QLabel("Architecture: —")
        self.lbl_res = QtWidgets.QLabel("Display: —")
        self.lbl_density = QtWidgets.QLabel("Density: —")
        self.lbl_storage = QtWidgets.QLabel("Storage: —")
        self.lbl_ram = QtWidgets.QLabel("RAM: —")
        self.lbl_conn = QtWidgets.QLabel("Interface: —")

        info_layout.addWidget(self.lbl_model, 0, 0)
        info_layout.addWidget(self.lbl_os, 0, 1)
        info_layout.addWidget(self.lbl_arch, 0, 2)
        info_layout.addWidget(self.lbl_conn, 0, 3)

        info_layout.addWidget(self.lbl_res, 1, 0)
        info_layout.addWidget(self.lbl_density, 1, 1)
        info_layout.addWidget(self.lbl_storage, 1, 2)
        info_layout.addWidget(self.lbl_ram, 1, 3)

        main_layout.addWidget(self.info_box)

    def _connect_signals(self) -> None:
        self.device_mgr.devices_updated.connect(self.update_devices_list)
        self.device_mgr.selected_device_changed.connect(self.update_device_details)
        self.device_mgr.status_changed.connect(self.update_status_badge)

    def update_devices_list(self, devices: List[DeviceItem]) -> None:
        """Repopulate the device selection dropdown."""
        self._block_signals = True
        current_serial = self.device_mgr.selected_serial
        self.device_combo.clear()

        if not devices:
            self.device_combo.addItem("No Android devices detected", "")
            self.device_combo.setEnabled(False)
            self._block_signals = False
            self.update_status_badge("", ConnectionState.DISCONNECTED.value)
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

    def update_status_badge(self, serial: str, state_str: str) -> None:
        """Update visual badge depending on connection state."""
        self.status_badge.setText(state_str)
        if state_str == ConnectionState.CONNECTED.value:
            self.status_badge.setObjectName("statusBadgeConnected")
        elif state_str in (ConnectionState.UNAUTHORIZED.value, ConnectionState.RECONNECTING.value):
            self.status_badge.setObjectName("statusBadgeWarning")
        else:
            self.status_badge.setObjectName("statusBadgeError")

        # Force stylesheet refresh
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def update_device_details(self, details: Optional[DeviceDetails]) -> None:
        """Refresh diagnostic specifications."""
        if not details:
            self.lbl_model.setText("Model: —")
            self.lbl_os.setText("Android OS: —")
            self.lbl_arch.setText("Architecture: —")
            self.lbl_res.setText("Display: —")
            self.lbl_density.setText("Density: —")
            self.lbl_storage.setText("Storage: —")
            self.lbl_ram.setText("RAM: —")
            self.lbl_conn.setText("Interface: —")
            return

        self.lbl_model.setText(f"Model: {details.manufacturer} {details.model}")
        self.lbl_os.setText(f"Android OS: {details.android_version} (API {details.sdk_level})")
        self.lbl_arch.setText(f"Architecture: {details.cpu_abi}")
        self.lbl_conn.setText(f"Interface: {details.connection_type}")

        phys = f"{details.physical_resolution[0]}×{details.physical_resolution[1]}"
        if details.override_resolution:
            res_text = f"Display: {phys} (Override: {details.override_resolution[0]}×{details.override_resolution[1]})"
        else:
            res_text = f"Display: {phys} (Native)"
        self.lbl_res.setText(res_text)

        dpi_text = f"{details.density} DPI" if details.density else "Unknown"
        self.lbl_density.setText(f"Density: {dpi_text}")
        self.lbl_storage.setText(f"Storage: {details.storage_free}")
        self.lbl_ram.setText(f"RAM: {details.ram_info}")
