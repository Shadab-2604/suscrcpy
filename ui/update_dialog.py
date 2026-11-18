"""GUI Update Dialog and Background Workers for SUSCRCPY.

Provides responsive, non-blocking GitHub release checking, release note display,
integrity verification, and atomic update installation.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from update_manager import (
    ArchiveSecurityError,
    ChecksumMismatchError,
    PermissionRequiredError,
    ReleaseInfo,
    UpdateError,
    UpdateManager,
)
from version import APP_NAME, APP_VERSION, GITHUB_URL

logger = logging.getLogger("suscrcpy.ui.update_dialog")


class UpdateCheckWorker(QtCore.QThread):
    """Background thread to query GitHub Releases API without blocking the UI."""

    check_finished = QtCore.Signal(object)  # ReleaseInfo
    check_failed = QtCore.Signal(str)       # Error message

    def __init__(self, manager: UpdateManager, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.manager = manager

    def run(self) -> None:
        try:
            release = self.manager.fetch_latest_release()
            self.check_finished.emit(release)
        except Exception as e:
            logger.error("Update check worker error: %s", e)
            self.check_failed.emit(str(e))


class UpdateInstallWorker(QtCore.QThread):
    """Background thread to download, verify, stage, and install update."""

    progress_updated = QtCore.Signal(str, float)  # status text, percentage (0.0 to 1.0)
    install_finished = QtCore.Signal(str)        # success message
    install_failed = QtCore.Signal(str)          # error message

    def __init__(
        self,
        manager: UpdateManager,
        release: ReleaseInfo,
        parent: Optional[QtCore.QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self.release = release

    def run(self) -> None:
        try:
            def on_progress(msg: str, pct: float) -> None:
                self.progress_updated.emit(msg, pct)

            result = self.manager.perform_update(
                release=self.release, progress_callback=on_progress
            )
            self.install_finished.emit(result)
        except Exception as e:
            logger.error("Update install worker error: %s", e)
            self.install_failed.emit(str(e))


class UpdateDialog(QtWidgets.QDialog):
    """Modal dialog for checking GitHub updates and triggering verified installation."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        install_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self.manager = UpdateManager(current_version=APP_VERSION, install_dir=install_dir)
        self._current_release: Optional[ReleaseInfo] = None
        self._check_worker: Optional[UpdateCheckWorker] = None
        self._install_worker: Optional[UpdateInstallWorker] = None

        self._build_ui()
        self.start_check()

    def _build_ui(self) -> None:
        self.setWindowTitle("SUSCRCPY Software Updates")
        self.resize(540, 420)
        self.setMinimumSize(480, 360)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header info
        title_box = QtWidgets.QHBoxLayout()
        icon_lbl = QtWidgets.QLabel("🔄")
        icon_lbl.setStyleSheet("font-size: 26px;")
        title_box.addWidget(icon_lbl)

        info_box = QtWidgets.QVBoxLayout()
        info_box.setSpacing(2)
        app_title = QtWidgets.QLabel(f"{APP_NAME} Software Update")
        app_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #EEEEEE;")
        info_box.addWidget(app_title)

        self.ver_lbl = QtWidgets.QLabel(f"Current installed version: {APP_VERSION}")
        self.ver_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        info_box.addWidget(self.ver_lbl)
        title_box.addLayout(info_box)
        title_box.addStretch()
        layout.addLayout(title_box)

        # Separator line
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet("color: #333333;")
        layout.addWidget(sep)

        # Status & Message Area
        self.status_lbl = QtWidgets.QLabel("Contacting GitHub for release updates...")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #4A90E2;")
        layout.addWidget(self.status_lbl)

        # Progress Bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #141414; border: 1px solid #333333; border-radius: 3px; height: 14px; text-align: center; } "
            "QProgressBar::chunk { background-color: #1E3A5F; }"
        )
        layout.addWidget(self.progress_bar)

        # Release Notes Group
        self.notes_group = QtWidgets.QGroupBox("Release Information")
        notes_layout = QtWidgets.QVBoxLayout(self.notes_group)
        notes_layout.setContentsMargins(8, 8, 8, 8)

        self.notes_text = QtWidgets.QPlainTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setStyleSheet(
            "background-color: #141414; color: #CCCCCC; border: 1px solid #282828; font-size: 11px;"
        )
        notes_layout.addWidget(self.notes_text)
        layout.addWidget(self.notes_group)

        # Action Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(8)

        self.github_btn = QtWidgets.QPushButton("🌐 View on GitHub")
        self.github_btn.setToolTip("Open GitHub release in web browser")
        self.github_btn.clicked.connect(self._open_github_release)
        btn_layout.addWidget(self.github_btn)

        btn_layout.addStretch()

        self.update_btn = QtWidgets.QPushButton("Update Now")
        self.update_btn.setObjectName("primaryBtn")
        self.update_btn.setEnabled(False)
        self.update_btn.clicked.connect(self._start_update)
        btn_layout.addWidget(self.update_btn)

        self.close_btn = QtWidgets.QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def start_check(self) -> None:
        """Begin non-blocking check for GitHub updates."""
        self.status_lbl.setText("Checking GitHub for the latest release...")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #4A90E2;")
        self.progress_bar.setRange(0, 0)  # Indeterminate animation
        self.update_btn.setEnabled(False)
        self.notes_text.setPlainText("Querying https://api.github.com...")

        self._check_worker = UpdateCheckWorker(self.manager, self)
        self._check_worker.check_finished.connect(self._on_check_finished)
        self._check_worker.check_failed.connect(self._on_check_failed)
        self._check_worker.start()

    def _on_check_finished(self, release: ReleaseInfo) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._current_release = release

        notes = f"Release: {release.name} ({release.tag_name})\nPublished: {release.published_at[:10]}\n\n{release.body}"
        self.notes_text.setPlainText(notes)

        if release.is_update_available:
            self.status_lbl.setText(f"★ New version available: {release.version}")
            self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #65B58A;")
            self.update_btn.setEnabled(True)
            self.update_btn.setText(f"Update to v{release.version}")
        else:
            self.status_lbl.setText(f"✓ SUSCRCPY is up to date (version {APP_VERSION}).")
            self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 500; color: #65B58A;")
            self.update_btn.setEnabled(False)

    def _on_check_failed(self, error_msg: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Failed to check for updates.")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #E05252;")
        self.notes_text.setPlainText(f"Error: {error_msg}\n\nPlease check your internet connection or try again later.")

    def _open_github_release(self) -> None:
        url = self._current_release.html_url if self._current_release else GITHUB_URL
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _start_update(self) -> None:
        if not self._current_release:
            return

        target_dir = self.manager.install_dir
        is_system_install = target_dir == Path("/opt/suscrcpy") or (target_dir.exists() and not os.access(target_dir, os.W_OK))

        if is_system_install and os.geteuid() != 0:
            # Check if pkexec is available for graphical authorization
            if shutil.which("pkexec"):
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Administrator Privileges Required",
                    f"Updating system installation at {target_dir} requires administrator permissions.\n\n"
                    "Would you like to authorize privilege escalation via pkexec to perform the update?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                )
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    self._run_pkexec_update()
                    return
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Administrator Privileges Required",
                    f"Updating the system-wide installation at {target_dir} requires root permissions.\n\n"
                    "Please run the following command in a terminal to complete the update:\n\n"
                    "    sudo suscrcpy --update",
                )
                return

        # Direct installation (when running with write access)
        self.update_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        self._install_worker = UpdateInstallWorker(self.manager, self._current_release, self)
        self._install_worker.progress_updated.connect(self._on_install_progress)
        self._install_worker.install_finished.connect(self._on_install_finished)
        self._install_worker.install_failed.connect(self._on_install_failed)
        self._install_worker.start()

    def _run_pkexec_update(self) -> None:
        """Run update with elevated privileges via pkexec."""
        self.status_lbl.setText("Waiting for administrator authorization...")
        QtWidgets.QApplication.processEvents()

        cmd = ["pkexec", "suscrcpy", "--update"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                QtWidgets.QMessageBox.information(
                    self,
                    "Update Succeeded",
                    "SUSCRCPY was updated successfully!\nPlease restart the application to use the new version.",
                )
                self.accept()
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Update Failed",
                    f"Administrator update failed or was cancelled.\n\n{res.stderr.strip()}",
                )
                self.status_lbl.setText("Update cancelled or failed.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Execution Error", str(e))

    def _on_install_progress(self, status: str, pct: float) -> None:
        self.status_lbl.setText(status)
        self.progress_bar.setValue(int(pct * 100))

    def _on_install_finished(self, msg: str) -> None:
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #65B58A;")
        self.progress_bar.setValue(100)
        self.close_btn.setEnabled(True)
        self.update_btn.setVisible(False)

        reply = QtWidgets.QMessageBox.question(
            self,
            "Update Complete",
            f"{msg}\n\nWould you like to restart SUSCRCPY now?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Restart application
            QtCore.QProcess.startDetached(sys.executable, sys.argv)
            QtWidgets.QApplication.quit()
        else:
            self.accept()

    def _on_install_failed(self, error: str) -> None:
        self.status_lbl.setText("Update installation failed.")
        self.status_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #E05252;")
        self.close_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        QtWidgets.QMessageBox.critical(self, "Update Failed", error)
