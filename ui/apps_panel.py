"""Installed application selector used to narrow logcat to one app."""
from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from core.app_manager import AppInfo, AppManager


class AppsPanel(QtWidgets.QWidget):
    """Search and select the application that logs should follow."""

    application_selected = QtCore.Signal(str)  # package name, "" for entire device
    refresh_requested = QtCore.Signal()

    def __init__(self, app_manager: AppManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.app_mgr = app_manager
        self._apps: List[AppInfo] = []
        self._selected_package = ""
        self._build_ui()
        self.app_mgr.apps_loaded.connect(self.set_applications)

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(6)
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search by app name or package")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_list)
        search_row.addWidget(self.search_input, stretch=1)

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setObjectName("ghostBtn")
        self.refresh_btn.clicked.connect(self.refresh_requested)
        search_row.addWidget(self.refresh_btn)
        layout.addLayout(search_row)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(12)
        self.filter_all = QtWidgets.QRadioButton("All")
        self.filter_all.setChecked(True)
        self.filter_user = QtWidgets.QRadioButton("User")
        self.filter_system = QtWidgets.QRadioButton("System")
        for button in (self.filter_all, self.filter_user, self.filter_system):
            button.toggled.connect(self._refresh_list)
            filter_row.addWidget(button)
        filter_row.addStretch(1)

        self.count_lbl = QtWidgets.QLabel("0 apps")
        self.count_lbl.setObjectName("mutedLabel")
        filter_row.addWidget(self.count_lbl)
        layout.addLayout(filter_row)

        self.app_list = QtWidgets.QListWidget()
        self.app_list.setAlternatingRowColors(False)
        self.app_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.app_list, stretch=1)

        self.selection_lbl = QtWidgets.QLabel("Logging: entire device")
        self.selection_lbl.setObjectName("mutedLabel")
        layout.addWidget(self.selection_lbl)

    # ---------------------------------------------------------------- data
    @property
    def selected_package(self) -> str:
        """Currently selected package, or an empty string for the whole device."""
        return self._selected_package

    def set_applications(self, apps: List[AppInfo]) -> None:
        self._apps = apps
        self._refresh_list()

    def _category(self) -> str:
        if self.filter_user.isChecked():
            return "user"
        if self.filter_system.isChecked():
            return "system"
        return "all"

    def _refresh_list(self) -> None:
        query = self.search_input.text().strip()
        filtered = self.app_mgr.filter_apps(self._apps, query=query, category=self._category())

        self.app_list.blockSignals(True)
        self.app_list.clear()
        for app in filtered:
            item = QtWidgets.QListWidgetItem(f"{app.display_name}   {app.package_name}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, app.package_name)
            item.setToolTip("System app" if app.is_system else "User app")
            self.app_list.addItem(item)
        self.app_list.blockSignals(False)

        self.count_lbl.setText(f"{len(filtered)} apps")

    def _on_selection_changed(
        self, current: Optional[QtWidgets.QListWidgetItem], _previous=None
    ) -> None:
        package = current.data(QtCore.Qt.ItemDataRole.UserRole) if current else ""
        if package:
            self._selected_package = package
            self.selection_lbl.setText(f"Logging: {package}")
            self.application_selected.emit(package)
        else:
            self.clear_selection()

    def clear_selection(self) -> None:
        self.app_list.blockSignals(True)
        self.app_list.setCurrentItem(None)
        self.app_list.clearSelection()
        self.app_list.blockSignals(False)
        self._selected_package = ""
        self.selection_lbl.setText("Logging: entire device")
        self.application_selected.emit("")
