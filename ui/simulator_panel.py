"""Platform Simulators Integration Panel (Mode 3) for SUSCRCPY 2.1.

Coordinates native Android SDK AVDs and Apple Xcode Simulators with transparent
workstation compatibility diagnostics.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.simulator_manager import SimulatorDevice, SimulatorManager
from ui.styles import COLOR_ACCENT, COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING

logger = logging.getLogger("suscrcpy.ui.simulator_panel")


class SimulatorPanel(QtWidgets.QWidget):
    """Panel for managing external platform simulators (Mode 3)."""

    def __init__(self, simulator_manager: SimulatorManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.sim_mgr = simulator_manager
        self._build_ui()
        self.refresh_avds()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Mode Header Banner
        banner = QtWidgets.QFrame()
        banner.setStyleSheet("background-color: #1f2d3d; border: 1px solid #388bfd; border-radius: 5px; padding: 6px;")
        b_layout = QtWidgets.QHBoxLayout(banner)
        b_layout.setContentsMargins(8, 4, 8, 4)

        b_title = QtWidgets.QLabel("💻 Mode 3: Platform Simulators Integration")
        b_title.setStyleSheet("font-weight: 700; color: #58a6ff; font-size: 13px;")
        b_layout.addWidget(b_title)

        b_desc = QtWidgets.QLabel("• Integrates external Android SDK Emulator (AVD) & Apple Xcode Simulator")
        b_desc.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        b_layout.addWidget(b_desc)
        b_layout.addStretch()
        layout.addWidget(banner)

        # Splitter between Android AVDs and Apple Simulators
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # 1. Android AVD Section
        avd_box = QtWidgets.QGroupBox("Android Emulator (AVDs)")
        avd_layout = QtWidgets.QVBoxLayout(avd_box)
        avd_layout.setSpacing(8)

        status_text = "Emulator Available" if self.sim_mgr.is_android_emulator_available else "Emulator Not Found in PATH/SDK"
        status_color = COLOR_SUCCESS if self.sim_mgr.is_android_emulator_available else COLOR_WARNING
        self.avd_status_lbl = QtWidgets.QLabel(f"● {status_text}")
        self.avd_status_lbl.setStyleSheet(f"color: {status_color}; font-weight: 600;")
        avd_layout.addWidget(self.avd_status_lbl)

        self.avd_table = QtWidgets.QTableWidget()
        self.avd_table.setColumnCount(3)
        self.avd_table.setHorizontalHeaderLabels(["AVD Name", "Type", "Status"])
        self.avd_table.horizontalHeader().setStretchLastSection(True)
        self.avd_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.avd_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        avd_layout.addWidget(self.avd_table)

        avd_btn_row = QtWidgets.QHBoxLayout()
        self.launch_btn = QtWidgets.QPushButton("▶ Launch Selected AVD")
        self.launch_btn.setObjectName("primaryButton")
        self.launch_btn.clicked.connect(self._launch_selected_avd)
        avd_btn_row.addWidget(self.launch_btn)

        self.refresh_btn = QtWidgets.QPushButton("↻ Refresh AVDs")
        self.refresh_btn.clicked.connect(self.refresh_avds)
        avd_btn_row.addWidget(self.refresh_btn)
        avd_layout.addLayout(avd_btn_row)

        splitter.addWidget(avd_box)

        # 2. Apple Xcode Simulator Section
        apple_box = QtWidgets.QGroupBox("Apple Simulator (Xcode)")
        apple_layout = QtWidgets.QVBoxLayout(apple_box)
        apple_layout.setSpacing(8)

        apple_status_text = "macOS Xcode Detected" if self.sim_mgr.is_apple_simulator_supported else "Unavailable on Linux/Windows"
        apple_status_color = COLOR_SUCCESS if self.sim_mgr.is_apple_simulator_supported else COLOR_WARNING
        self.apple_status_lbl = QtWidgets.QLabel(f"● {apple_status_text}")
        self.apple_status_lbl.setStyleSheet(f"color: {apple_status_color}; font-weight: 600;")
        apple_layout.addWidget(self.apple_status_lbl)

        # Explanatory Card
        info_card = QtWidgets.QFrame()
        info_card.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px;")
        ic_layout = QtWidgets.QVBoxLayout(info_card)
        ic_text = QtWidgets.QLabel(self.sim_mgr.get_apple_support_notice())
        ic_text.setWordWrap(True)
        ic_text.setStyleSheet("color: #c9d1d9; font-size: 12px; line-height: 1.4;")
        ic_layout.addWidget(ic_text)
        apple_layout.addWidget(info_card)

        apple_layout.addStretch()
        splitter.addWidget(apple_box)

        layout.addWidget(splitter)

    def refresh_avds(self) -> None:
        """Scan and display configured AVDs."""
        avds = self.sim_mgr.list_android_avds()
        self.avd_table.setRowCount(len(avds))

        for row, avd in enumerate(avds):
            item_name = QtWidgets.QTableWidgetItem(avd.name)
            item_name.setData(QtCore.Qt.ItemDataRole.UserRole, avd)
            item_type = QtWidgets.QTableWidgetItem(avd.device_type.title())
            item_status = QtWidgets.QTableWidgetItem(avd.status.title())

            self.avd_table.setItem(row, 0, item_name)
            self.avd_table.setItem(row, 1, item_type)
            self.avd_table.setItem(row, 2, item_status)

    def _launch_selected_avd(self) -> None:
        selected = self.avd_table.selectedItems()
        if not selected:
            QtWidgets.QMessageBox.information(self, "No AVD Selected", "Please select an AVD from the table to launch.")
            return

        avd: SimulatorDevice = self.avd_table.item(selected[0].row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if avd:
            try:
                self.sim_mgr.launch_android_avd(avd.name)
                QtWidgets.QMessageBox.information(
                    self, "Launching AVD", f"Android Virtual Device '{avd.name}' started in background."
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Launch Error", f"Failed to launch AVD '{avd.name}':\n{e}")
