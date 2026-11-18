"""Android Logcat monitoring panel for SUSCRCPY.

Supports Full Device and Application-specific logging, real-time crash and error detection,
severity coloring, bounded memory buffer, buffer clearing, and structured exports.
"""
from __future__ import annotations

import html
import logging
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.device_manager import DeviceDetails
from core.error_detector import LogSeverity
from core.log_exporter import LogExporter
from core.log_manager import LogEntry, LogManager
from ui.styles import (
    COLOR_ACCENT,
    COLOR_CRASH,
    COLOR_ERROR,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_BRIGHT,
    COLOR_TEXT_MUTED,
    COLOR_WARNING,
)

logger = logging.getLogger("suscrcpy.ui.logs_panel")

SEVERITY_COLORS = {
    LogSeverity.VERBOSE.value: COLOR_TEXT_MUTED,
    LogSeverity.DEBUG.value: "#a5d6ff",
    LogSeverity.INFO.value: COLOR_TEXT_BRIGHT,
    LogSeverity.WARNING.value: COLOR_WARNING,
    LogSeverity.ERROR.value: COLOR_ERROR,
    LogSeverity.FATAL.value: COLOR_CRASH,
}


class LogsPanel(QtWidgets.QWidget):
    """Panel for real-time logcat streaming, crash detection, filtering, and export."""

    start_requested = QtCore.Signal()
    stop_requested = QtCore.Signal()
    clear_device_buffer_requested = QtCore.Signal()

    def __init__(
        self,
        log_manager: LogManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.log_mgr = log_manager
        self._target_package: Optional[str] = None
        self._device_details: Optional[DeviceDetails] = None
        self._auto_scroll = True
        self._search_term = ""

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)

        # Top Control Bar Row 1: Mode, Action Buttons, Search, Stats
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(8)

        # Mode selector
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Full Android Device Logs", "full")
        self.mode_combo.addItem("Selected Application Logs", "app")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        row1.addWidget(self.mode_combo)

        # Start / Stop Buttons
        self.start_btn = QtWidgets.QPushButton("▶ Start Logs")
        self.start_btn.setObjectName("successButton")
        self.start_btn.clicked.connect(self.start_requested)
        row1.addWidget(self.start_btn)

        self.stop_btn = QtWidgets.QPushButton("⏹ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested)
        row1.addWidget(self.stop_btn)

        # Pause / Resume Button
        self.pause_btn = QtWidgets.QPushButton("⏸ Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCheckable(True)
        self.pause_btn.clicked.connect(self._toggle_pause)
        row1.addWidget(self.pause_btn)

        # Clear View Button
        self.clear_view_btn = QtWidgets.QPushButton("Clear View")
        self.clear_view_btn.clicked.connect(self._clear_view)
        row1.addWidget(self.clear_view_btn)

        # Clear Device Buffer Button
        self.clear_device_btn = QtWidgets.QPushButton("Clear Device Buffer")
        self.clear_device_btn.setObjectName("dangerButton")
        self.clear_device_btn.setToolTip("Executes 'adb logcat -c' (removes Android buffer)")
        self.clear_device_btn.clicked.connect(self._confirm_clear_device_buffer)
        row1.addWidget(self.clear_device_btn)

        # Download Button
        self.download_btn = QtWidgets.QPushButton("💾 Download Logs")
        self.download_btn.clicked.connect(self._export_logs)
        row1.addWidget(self.download_btn)

        row1.addStretch()

        # Stats Badge
        self.stats_label = QtWidgets.QLabel("Errors: 0  |  Warnings: 0  |  Crashes: 0")
        self.stats_label.setStyleSheet(
            "background-color: #161b22; border: 1px solid #30363d; border-radius: 4px; "
            "padding: 4px 10px; font-weight: 600;"
        )
        row1.addWidget(self.stats_label)

        layout.addLayout(row1)

        # Row 2: Search Bar, Auto-scroll, App Target indicator
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(10)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Filter live logs by text / tag / PID...")
        self.search_input.textChanged.connect(self._on_search_changed)
        row2.addWidget(self.search_input, stretch=2)

        self.autoscroll_cb = QtWidgets.QCheckBox("Auto-scroll")
        self.autoscroll_cb.setChecked(True)
        self.autoscroll_cb.stateChanged.connect(self._on_autoscroll_toggled)
        row2.addWidget(self.autoscroll_cb)

        self.target_app_label = QtWidgets.QLabel("Target: Entire Device")
        self.target_app_label.setStyleSheet("color: #8b949e; font-style: italic;")
        row2.addWidget(self.target_app_label, stretch=1)

        layout.addLayout(row2)

        # Crash Alert Notification (Hidden by default)
        self.crash_alert_banner = QtWidgets.QLabel("⚠️ APPLICATION CRASH DETECTED")
        self.crash_alert_banner.setObjectName("crashBanner")
        self.crash_alert_banner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.crash_alert_banner.setVisible(False)
        layout.addWidget(self.crash_alert_banner)

        # Plain Text Logcat Viewer
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(3000)  # Safe bounded display memory buffer
        layout.addWidget(self.log_text)

    def _connect_signals(self) -> None:
        self.log_mgr.new_logs_batch.connect(self.append_log_batch)
        self.log_mgr.stats_updated.connect(self.update_stats)
        self.log_mgr.status_updated.connect(self._on_status_updated)
        self.log_mgr.crash_alert.connect(self._on_crash_detected)

    def set_device_details(self, details: Optional[DeviceDetails]) -> None:
        """Store device details for export header."""
        self._device_details = details

    def set_target_package(self, package_name: Optional[str]) -> None:
        """Set the active target application package."""
        self._target_package = package_name
        if package_name:
            self.mode_combo.setCurrentIndex(1)
            self.target_app_label.setText(f"Target: {package_name}")
        else:
            self.mode_combo.setCurrentIndex(0)
            self.target_app_label.setText("Target: Entire Device")

    def get_selected_mode(self) -> str:
        """Return 'full' or 'app'."""
        return self.mode_combo.currentData()

    def _on_mode_changed(self, index: int) -> None:
        mode = self.mode_combo.itemData(index)
        if mode == "app" and not self._target_package:
            self.target_app_label.setText("Target: None selected (select app from panel)")
        elif mode == "app":
            self.target_app_label.setText(f"Target: {self._target_package}")
        else:
            self.target_app_label.setText("Target: Entire Device")

    def _toggle_pause(self) -> None:
        if self.pause_btn.isChecked():
            self.pause_btn.setText("▶ Resume")
            self.log_mgr.pause_capture()
        else:
            self.pause_btn.setText("⏸ Pause")
            self.log_mgr.resume_capture()

    def set_streaming_active(self, active: bool) -> None:
        """Update button enabled states."""
        self.start_btn.setEnabled(not active)
        self.stop_btn.setEnabled(active)
        self.pause_btn.setEnabled(active)
        if not active:
            self.pause_btn.setChecked(False)
            self.pause_btn.setText("⏸ Pause")

    def _clear_view(self) -> None:
        self.log_text.clear()
        self.crash_alert_banner.setVisible(False)
        self.log_mgr.clear_view()

    def _confirm_clear_device_buffer(self) -> None:
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Clear Device Buffer",
            "This will execute 'adb logcat -c', permanently erasing the Android device's "
            "hardware log buffers. Useful diagnostic evidence will be cleared.\n\n"
            "Are you sure you want to proceed?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.clear_device_buffer_requested.emit()

    def _on_search_changed(self, text: str) -> None:
        self._search_term = text.strip().lower()

    def _on_autoscroll_toggled(self, state: int) -> None:
        self._auto_scroll = bool(state)

    def append_log_batch(self, batch: List[LogEntry]) -> None:
        """Render new log batch with color formatting and search filtering."""
        if not batch:
            return

        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)

        for entry in batch:
            # Check search filter
            if self._search_term:
                searchable = f"{entry.tag} {entry.message} {entry.pid}".lower()
                if self._search_term not in searchable:
                    continue

            # Choose format based on severity / crash
            char_format = QtGui.QTextCharFormat()
            if entry.detection.is_crash:
                char_format.setForeground(QtGui.QColor(COLOR_CRASH))
                char_format.setFontWeight(QtGui.QFont.Weight.Bold)
            elif entry.detection.is_error:
                char_format.setForeground(QtGui.QColor(COLOR_ERROR))
                char_format.setFontWeight(QtGui.QFont.Weight.Bold)
            elif entry.detection.is_warning:
                char_format.setForeground(QtGui.QColor(COLOR_WARNING))
            elif entry.level == "D":
                char_format.setForeground(QtGui.QColor("#a5d6ff"))
            elif entry.level == "V":
                char_format.setForeground(QtGui.QColor(COLOR_TEXT_MUTED))
            else:
                char_format.setForeground(QtGui.QColor(COLOR_TEXT))

            cursor.insertText(f"{entry.raw}\n", char_format)

        if self._auto_scroll:
            self.log_text.ensureCursorVisible()

    def update_stats(self, errors: int, warnings: int, crashes: int) -> None:
        """Update live statistics counter."""
        self.stats_label.setText(f"Errors: {errors}  |  Warnings: {warnings}  |  Crashes: {crashes}")
        if crashes > 0:
            self.stats_label.setStyleSheet(
                f"background-color: #4c1d24; border: 1px solid {COLOR_CRASH}; border-radius: 4px; "
                "padding: 4px 10px; font-weight: 700; color: #ff7b72;"
            )
        elif errors > 0:
            self.stats_label.setStyleSheet(
                f"background-color: #3b1e22; border: 1px solid {COLOR_ERROR}; border-radius: 4px; "
                "padding: 4px 10px; font-weight: 600; color: #ffa198;"
            )
        else:
            self.stats_label.setStyleSheet(
                "background-color: #161b22; border: 1px solid #30363d; border-radius: 4px; "
                "padding: 4px 10px; font-weight: 600;"
            )

    def _on_crash_detected(self, entry: LogEntry) -> None:
        """Display visible crash banner."""
        reason = entry.detection.crash_reason or "Fatal Exception"
        self.crash_alert_banner.setText(f"🚨 APPLICATION CRASH DETECTED: {reason} (PID {entry.pid})")
        self.crash_alert_banner.setVisible(True)

    def _on_status_updated(self, msg: str) -> None:
        logger.debug("Log status: %s", msg)

    def _export_logs(self) -> None:
        """Open native Save File dialog and export captured logcat records."""
        logs = self.log_mgr.export_buffer
        if not logs:
            QtWidgets.QMessageBox.information(
                self, "Export Logs", "No logs have been captured in this session yet."
            )
            return

        model_name = self._device_details.model if self._device_details else "device"
        target_name = self._target_package or "full_device"
        default_name = LogExporter.generate_default_filename(model_name, target_name)

        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Android Device Logs",
            default_name,
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)",
        )
        if not filepath:
            return

        try:
            count = LogExporter.export_to_file(
                filepath=filepath,
                logs=logs,
                details=self._device_details,
                mode=self.log_mgr.mode_label,
                start_time=self.log_mgr.start_time,
            )
            QtWidgets.QMessageBox.information(
                self, "Export Successful", f"Successfully exported {count} log entries to:\n{filepath}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Failed to save log file:\n{e}")
