"""Installed Android applications discovery panel for SUSCRCPY.

Lists user and system applications, supports filtering and search, displays package details,
and directly feeds the selected app into application-specific log monitoring.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.app_manager import AppInfo, AppManager

logger = logging.getLogger("suscrcpy.ui.application_panel")


class ApplicationPanel(QtWidgets.QWidget):
    """Panel for browsing, filtering, and targeting installed Android packages."""

    app_selected = QtCore.Signal(object)  # AppInfo
    monitor_app_requested = QtCore.Signal(str)  # package_name
    refresh_requested = QtCore.Signal()

    def __init__(
        self,
        app_manager: AppManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.app_mgr = app_manager
        self._all_apps: List[AppInfo] = []
        self._current_filter = "all"
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Header with Search and Refresh
        search_row = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search by name or package...")
        self.search_input.textChanged.connect(self._apply_filter)
        search_row.addWidget(self.search_input)

        self.refresh_btn = QtWidgets.QPushButton("↻")
        self.refresh_btn.setToolTip("Refresh application list from device")
        self.refresh_btn.setMaximumWidth(36)
        self.refresh_btn.clicked.connect(self.refresh_requested)
        search_row.addWidget(self.refresh_btn)
        layout.addLayout(search_row)

        # Filter Tabs / Radio
        filter_row = QtWidgets.QHBoxLayout()
        self.filter_group = QtWidgets.QButtonGroup(self)

        self.radio_all = QtWidgets.QRadioButton("All Apps")
        self.radio_all.setChecked(True)
        self.filter_group.addButton(self.radio_all)
        filter_row.addWidget(self.radio_all)

        self.radio_user = QtWidgets.QRadioButton("User Apps")
        self.filter_group.addButton(self.radio_user)
        filter_row.addWidget(self.radio_user)

        self.radio_system = QtWidgets.QRadioButton("System Apps")
        self.filter_group.addButton(self.radio_system)
        filter_row.addWidget(self.radio_system)

        filter_row.addStretch()
        self.filter_group.buttonClicked.connect(self._on_category_changed)
        layout.addLayout(filter_row)

        # Applications Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Application / Package", "Type", "Version"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        # Bottom Actions Row
        actions_row = QtWidgets.QHBoxLayout()
        self.copy_pkg_btn = QtWidgets.QPushButton("📋 Copy Package")
        self.copy_pkg_btn.setEnabled(False)
        self.copy_pkg_btn.clicked.connect(self._on_copy_package)
        actions_row.addWidget(self.copy_pkg_btn)

        self.monitor_btn = QtWidgets.QPushButton("⚡ Target App for Logs")
        self.monitor_btn.setObjectName("primaryButton")
        self.monitor_btn.setEnabled(False)
        self.monitor_btn.clicked.connect(self._on_target_for_logs)
        actions_row.addWidget(self.monitor_btn)

        layout.addLayout(actions_row)

    def _connect_signals(self) -> None:
        self.app_mgr.apps_loaded.connect(self.set_applications)

    def set_applications(self, apps: List[AppInfo]) -> None:
        """Update full applications list."""
        self._all_apps = apps
        self._apply_filter()

    def _on_category_changed(self) -> None:
        if self.radio_user.isChecked():
            self._current_filter = "user"
        elif self.radio_system.isChecked():
            self._current_filter = "system"
        else:
            self._current_filter = "all"
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.search_input.text()
        filtered = self.app_mgr.filter_apps(self._all_apps, query=query, category=self._current_filter)

        self.table.setRowCount(len(filtered))
        for row, app in enumerate(filtered):
            # Display name and package
            item_name = QtWidgets.QTableWidgetItem(f"{app.display_name}\n{app.package_name}")
            item_name.setData(QtCore.Qt.ItemDataRole.UserRole, app)

            item_type = QtWidgets.QTableWidgetItem(app.category_label)
            item_type.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            item_ver = QtWidgets.QTableWidgetItem(app.version_name)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_type)
            self.table.setItem(row, 2, item_ver)

        self.copy_pkg_btn.setEnabled(False)
        self.monitor_btn.setEnabled(False)

    def _on_selection_changed(self) -> None:
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            self.copy_pkg_btn.setEnabled(False)
            self.monitor_btn.setEnabled(False)
            return

        item = self.table.item(selected_rows[0].row(), 0)
        if item:
            app = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if app:
                self.copy_pkg_btn.setEnabled(True)
                self.monitor_btn.setEnabled(True)
                self.app_selected.emit(app)

    def _on_copy_package(self) -> None:
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        item = self.table.item(selected_rows[0].row(), 0)
        if item:
            app: AppInfo = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if app:
                QtWidgets.QApplication.clipboard().setText(app.package_name)

    def _on_target_for_logs(self) -> None:
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        item = self.table.item(selected_rows[0].row(), 0)
        if item:
            app: AppInfo = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if app:
                self.monitor_app_requested.emit(app.package_name)
