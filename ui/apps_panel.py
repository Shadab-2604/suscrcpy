"""Installed application list and APK installation for the connected device."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from core.apk_installer import ApkInstallError, ApkInstaller, InstallResult
from core.app_manager import AppInfo, AppManager

logger = logging.getLogger("suscrcpy.ui.apps_panel")


class AppsPanel(QtWidgets.QWidget):
    """Install APKs, then search/select the application that logs should follow."""

    application_selected = QtCore.Signal(str)  # package name, "" for entire device
    refresh_requested = QtCore.Signal()
    apk_installed = QtCore.Signal(str)  # APK file name

    def __init__(
        self,
        app_manager: AppManager,
        installer: Optional[ApkInstaller] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.app_mgr = app_manager
        self.installer = installer
        self._apps: List[AppInfo] = []
        self._selected_package = ""
        self._serial: Optional[str] = None
        self._build_ui()
        self.app_mgr.apps_loaded.connect(self.set_applications)
        if self.installer is not None:
            self.installer.progress.connect(self._on_install_progress)
            self.installer.finished.connect(self._on_install_finished)
        self.set_device_serial(None)

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._build_install_card())

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

    def _build_install_card(self) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setObjectName("cardPanel")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(7)

        title_row = QtWidgets.QHBoxLayout()
        title_row.setSpacing(8)
        title = QtWidgets.QLabel("Install APK")
        title.setObjectName("cardTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)

        self.install_state_lbl = QtWidgets.QLabel("No device")
        self.install_state_lbl.setObjectName("mutedLabel")
        title_row.addWidget(self.install_state_lbl)
        card_layout.addLayout(title_row)

        path_row = QtWidgets.QHBoxLayout()
        path_row.setSpacing(6)
        self.apk_path_input = QtWidgets.QLineEdit()
        self.apk_path_input.setPlaceholderText("Path to an .apk file on this PC")
        self.apk_path_input.setClearButtonEnabled(True)
        self.apk_path_input.returnPressed.connect(self._on_install_clicked)
        self.apk_path_input.textChanged.connect(self._on_path_changed)
        path_row.addWidget(self.apk_path_input, stretch=1)

        self.browse_btn = QtWidgets.QPushButton("Browse…")
        self.browse_btn.setToolTip("Pick an APK file from this computer")
        self.browse_btn.clicked.connect(self._browse_apk)
        path_row.addWidget(self.browse_btn)
        card_layout.addLayout(path_row)

        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(8)
        self.install_btn = QtWidgets.QPushButton("Install on device")
        self.install_btn.setObjectName("primaryBtn")
        self.install_btn.setToolTip("Install this APK on the connected device (replaces the same package)")
        self.install_btn.clicked.connect(self._on_install_clicked)
        action_row.addWidget(self.install_btn)

        self.install_result_lbl = QtWidgets.QLabel("")
        self.install_result_lbl.setWordWrap(True)
        self.install_result_lbl.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.install_result_lbl.setVisible(False)
        action_row.addWidget(self.install_result_lbl, stretch=1)
        card_layout.addLayout(action_row)

        self.install_progress = QtWidgets.QProgressBar()
        self.install_progress.setRange(0, 0)
        self.install_progress.setTextVisible(False)
        self.install_progress.setFixedHeight(4)
        self.install_progress.setVisible(False)
        card_layout.addWidget(self.install_progress)

        return card

    # -------------------------------------------------------------- device
    def set_device_serial(self, serial: Optional[str]) -> None:
        """Switching devices invalidates nothing user typed, only the ability to install."""
        self._serial = serial or None
        self.install_state_lbl.setText("Ready" if self._serial else "No device")
        self.install_state_lbl.setToolTip(self._serial or "Select a connected device to install")
        self._update_install_enabled()

    def _update_install_enabled(self) -> None:
        busy = bool(self.installer and self.installer.is_installing)
        has_path = bool(self.apk_path_input.text().strip())
        self.install_btn.setEnabled(self._serial is not None and has_path and not busy)
        self.browse_btn.setEnabled(not busy)
        self.install_btn.setText("Installing…" if busy else "Install on device")

    def _on_path_changed(self, _text: str) -> None:
        self._update_install_enabled()

    # ------------------------------------------------------------- install
    def _browse_apk(self) -> None:
        start_dir = self.apk_path_input.text().strip() or str(Path.home())
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select APK to install",
            start_dir,
            "Android packages (*.apk);;All files (*)",
        )
        if path:
            self.apk_path_input.setText(path)

    def _on_install_clicked(self) -> None:
        if self.installer is None:
            self._show_result(InstallResult(False, "Installer is not available."), None)
            return
        try:
            self.installer.install(self._serial, self.apk_path_input.text())
        except ApkInstallError as exc:
            self._show_result(InstallResult(False, str(exc)), None)

    def _on_install_progress(self, message: str) -> None:
        self.install_progress.setVisible(True)
        self.install_result_lbl.setVisible(False)
        self.install_state_lbl.setText(message)
        self._update_install_enabled()

    def _on_install_finished(self, result: InstallResult) -> None:
        self.install_progress.setVisible(False)
        self._update_install_enabled()
        apk_name = Path(self.apk_path_input.text().strip()).name
        self._show_result(result, apk_name)

        if result.success:
            self.install_state_lbl.setText(f"Installed {apk_name}")
            self.apk_installed.emit(apk_name)
        else:
            self.install_state_lbl.setText("Install failed")

    def _show_result(self, result: InstallResult, _apk_name: Optional[str] = None) -> None:
        self.install_result_lbl.setObjectName("installOk" if result.success else "installError")
        self.install_result_lbl.setText(result.message)
        self.install_result_lbl.style().unpolish(self.install_result_lbl)
        self.install_result_lbl.style().polish(self.install_result_lbl)
        self.install_result_lbl.setToolTip(result.output or result.message)
        self.install_result_lbl.setVisible(True)

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
