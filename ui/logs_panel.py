"""Live Android logcat viewer with exact classification, filters and exports.

Every line is classified once by :class:`core.error_detector.ErrorDetector`. The panel
keeps the last ``VIEW_LIMIT`` entries in memory so changing a filter re-renders from
real data instead of only affecting future lines.
"""
from __future__ import annotations

import logging
import os
import time
from typing import List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from core.device_manager import DeviceDetails
from core.error_detector import ErrorDetector
from core.log_exporter import LogExporter
from core.log_manager import LogEntry, LogManager

logger = logging.getLogger("suscrcpy.ui.logs_panel")

COLOR_TEXT = "#E6EDF3"
COLOR_MUTED = "#8B949E"
COLOR_WARNING = "#D9A441"
COLOR_ERROR = "#E05252"
COLOR_CRASH = "#FF6B6B"

VIEW_LIMIT = 3000

CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("all", "All"),
    ("error", "Errors"),
    ("warning", "Warnings"),
    ("crash", "Crashes"),
)


def matches_category(entry: LogEntry, category: str) -> bool:
    """Exact category test used by the view, the counters and the exports."""
    if category == "error":
        return entry.detection.is_error
    if category == "warning":
        return entry.detection.is_warning
    if category == "crash":
        return entry.detection.is_crash
    return True


class LogsPanel(QtWidgets.QWidget):
    """Streams logcat into a bounded, exactly-filterable view."""

    start_requested = QtCore.Signal()
    stop_requested = QtCore.Signal()

    def __init__(self, log_manager: LogManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.log_mgr = log_manager
        self._device_details: Optional[DeviceDetails] = None
        self._target_package: Optional[str] = None
        self._search_term = ""
        self._category = "all"
        self._auto_scroll = True
        self._entries: List[LogEntry] = []
        self._counts: Tuple[int, int, int] = (0, 0, 0)
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(6)

        self.toggle_btn = QtWidgets.QPushButton("Start logs")
        self.toggle_btn.setObjectName("primaryBtn")
        self.toggle_btn.setMinimumWidth(104)
        self.toggle_btn.clicked.connect(self._on_toggle)
        controls.addWidget(self.toggle_btn)

        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause_toggle)
        controls.addWidget(self.pause_btn)

        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.setToolTip("Clear the visible log rows (the device buffer is untouched)")
        self.clear_btn.clicked.connect(self._on_clear_view)
        controls.addWidget(self.clear_btn)

        self.reset_btn = QtWidgets.QPushButton("Reset counters")
        self.reset_btn.setToolTip("Set the error, warning and crash counters back to zero")
        self.reset_btn.clicked.connect(self._on_reset_counters)
        controls.addWidget(self.reset_btn)

        controls.addStretch(1)

        self.export_btn = QtWidgets.QToolButton()
        self.export_btn.setText("Export \u25be")
        self.export_btn.setObjectName("subtleBtn")
        self.export_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.export_btn.setToolTip("Download all logs, or only one category")
        self._build_export_menu()
        controls.addWidget(self.export_btn)
        layout.addLayout(controls)

        # Exact category filter, with live counts baked into the labels.
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(8)

        segment = QtWidgets.QFrame()
        segment.setObjectName("segmentedControl")
        segment_layout = QtWidgets.QHBoxLayout(segment)
        segment_layout.setContentsMargins(3, 3, 3, 3)
        segment_layout.setSpacing(2)

        self._segment_group = QtWidgets.QButtonGroup(self)
        self._segment_group.setExclusive(True)
        self._segment_buttons = {}
        for index, (key, label) in enumerate(CATEGORIES):
            button = QtWidgets.QPushButton(label)
            button.setObjectName("segmentBtn")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, value=key: self._on_category_changed(value))
            self._segment_group.addButton(button, index)
            segment_layout.addWidget(button)
            self._segment_buttons[key] = button

        filter_row.addWidget(segment)
        filter_row.addStretch(1)

        self.line_count_lbl = QtWidgets.QLabel("0 lines")
        self.line_count_lbl.setObjectName("mutedLabel")
        filter_row.addWidget(self.line_count_lbl)
        layout.addLayout(filter_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Filter by tag, message or pid")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_input, stretch=1)

        self.autoscroll_cb = QtWidgets.QCheckBox("Auto-scroll")
        self.autoscroll_cb.setChecked(True)
        self.autoscroll_cb.toggled.connect(lambda checked: setattr(self, "_auto_scroll", checked))
        search_row.addWidget(self.autoscroll_cb)
        layout.addLayout(search_row)

        self.crash_banner = QtWidgets.QLabel("")
        self.crash_banner.setObjectName("crashBanner")
        self.crash_banner.setVisible(False)
        layout.addWidget(self.crash_banner)

        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setObjectName("logView")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(VIEW_LIMIT)
        self.log_text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.log_text, stretch=1)

        self._update_segment_labels()

    def _build_export_menu(self) -> None:
        menu = QtWidgets.QMenu(self.export_btn)
        menu.addAction("Save all logs…", lambda: self._on_export("all"))
        menu.addSeparator()
        menu.addAction("Save errors only…", lambda: self._on_export("error"))
        menu.addAction("Save warnings only…", lambda: self._on_export("warning"))
        menu.addAction("Save crashes only…", lambda: self._on_export("crash"))
        self.export_btn.setMenu(menu)

    def _connect_signals(self) -> None:
        self.log_mgr.new_logs_batch.connect(self.append_batch)
        self.log_mgr.stats_updated.connect(self.update_stats)
        self.log_mgr.crash_alert.connect(self._on_crash)

    # --------------------------------------------------------------- state
    def set_device_details(self, details: Optional[DeviceDetails]) -> None:
        self._device_details = details

    def set_target_package(self, package: str) -> None:
        self._target_package = package or None

    def set_streaming_active(self, active: bool) -> None:
        self.toggle_btn.setText("Stop logs" if active else "Start logs")
        self.toggle_btn.setObjectName("dangerBtn" if active else "primaryBtn")
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.pause_btn.setEnabled(active)
        if not active:
            self.pause_btn.setChecked(False)
            self.pause_btn.setText("Pause")

    # ------------------------------------------------------------- actions
    def _on_toggle(self) -> None:
        if self.log_mgr.is_streaming:
            self.stop_requested.emit()
        else:
            self.start_requested.emit()

    def _on_pause_toggle(self) -> None:
        if self.pause_btn.isChecked():
            self.pause_btn.setText("Resume")
            self.log_mgr.pause_capture()
            self._auto_scroll = False
            self.autoscroll_cb.setChecked(False)
        else:
            self.pause_btn.setText("Pause")
            self.log_mgr.resume_capture()
            self._auto_scroll = True
            self.autoscroll_cb.setChecked(True)

    def _on_clear_view(self) -> None:
        """Clear rows only; captured history and counters stay intact."""
        self._entries.clear()
        self.log_text.clear()
        self.crash_banner.setVisible(False)
        self._update_line_count()

    def _on_reset_counters(self) -> None:
        """Zero the error/warning/crash counters without dropping captured logs."""
        self.log_mgr.reset_statistics()
        self.crash_banner.setVisible(False)
        self.update_stats(0, 0, 0)

    def _on_search_changed(self, text: str) -> None:
        self._search_term = text.strip().lower()
        self._rerender()

    def _on_category_changed(self, category: str) -> None:
        if category == self._category:
            return
        self._category = category
        self._rerender()

    # ------------------------------------------------------------- render
    def _entry_visible(self, entry: LogEntry) -> bool:
        if not matches_category(entry, self._category):
            return False
        if self._search_term:
            haystack = f"{entry.tag} {entry.message} {entry.pid}".lower()
            return self._search_term in haystack
        return True

    def _insert_entry(self, cursor: QtGui.QTextCursor, entry: LogEntry) -> None:
        fmt = QtGui.QTextCharFormat()
        if entry.detection.is_crash:
            fmt.setForeground(QtGui.QColor(COLOR_CRASH))
            fmt.setFontWeight(QtGui.QFont.Weight.Bold)
        elif entry.detection.is_error:
            fmt.setForeground(QtGui.QColor(COLOR_ERROR))
        elif entry.detection.is_warning:
            fmt.setForeground(QtGui.QColor(COLOR_WARNING))
        elif entry.level == "V":
            fmt.setForeground(QtGui.QColor(COLOR_MUTED))
        else:
            fmt.setForeground(QtGui.QColor(COLOR_TEXT))
        cursor.insertText(entry.raw + "\n", fmt)

    def append_batch(self, batch: List[LogEntry]) -> None:
        if not batch:
            return

        self._entries.extend(batch)
        overflow = len(self._entries) - VIEW_LIMIT
        if overflow > 0:
            del self._entries[:overflow]

        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        inserted = False
        for entry in batch:
            if self._entry_visible(entry):
                self._insert_entry(cursor, entry)
                inserted = True

        if inserted and self._auto_scroll:
            self.log_text.ensureCursorVisible()
        self._update_line_count()

    def _rerender(self) -> None:
        """Re-render the retained window so filter changes apply to existing rows."""
        self.log_text.clear()
        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        for entry in self._entries:
            if self._entry_visible(entry):
                self._insert_entry(cursor, entry)
        if self._auto_scroll:
            self.log_text.ensureCursorVisible()
        self._update_line_count()

    # --------------------------------------------------------------- notes
    def note(self, message: str) -> None:
        """Add a local workstation line (for example an APK install) to the log view."""
        stamp = time.strftime("%m-%d %H:%M:%S.000")
        pid = os.getpid()
        detection = ErrorDetector().analyze("I", "SUSCRCPY", message, pid=pid)
        entry = LogEntry(
            timestamp=stamp,
            pid=pid,
            tid=pid,
            level="I",
            tag="SUSCRCPY",
            message=message,
            raw=f"{stamp} {pid:5d} {pid:5d} I SUSCRCPY: {message}",
            detection=detection,
        )
        self.append_batch([entry])

    def _update_line_count(self) -> None:
        matching = sum(1 for entry in self._entries if self._entry_visible(entry))
        self.line_count_lbl.setText(
            f"{matching:,} matching · {len(self._entries):,} kept"
        )

    def update_stats(self, errors: int, warnings: int, crashes: int) -> None:
        self._counts = (errors, warnings, crashes)
        self._update_segment_labels()

    def _update_segment_labels(self) -> None:
        errors, warnings, crashes = self._counts
        values = {"all": None, "error": errors, "warning": warnings, "crash": crashes}
        for key, label in CATEGORIES:
            count = values[key]
            text = label if count is None else f"{label} {count}"
            self._segment_buttons[key].setText(text)
        self._segment_buttons["error"].setToolTip(f"{errors} error-level lines (includes crashes)")
        self._segment_buttons["warning"].setToolTip(f"{warnings} warning-level lines")
        self._segment_buttons["crash"].setToolTip(f"{crashes} crash events (stack frames grouped)")
        self.reset_btn.setEnabled(any((errors, warnings, crashes)))

    def _on_crash(self, entry: LogEntry) -> None:
        reason = entry.detection.crash_reason or "Fatal exception"
        self.crash_banner.setText(f"Crash detected: {reason} (pid {entry.pid})")
        self.crash_banner.setVisible(True)

    # ------------------------------------------------------------- export
    def _on_export(self, scope: str) -> None:
        allowed = {"all", "error", "warning", "crash"}
        scope = scope if scope in allowed else "all"
        logs = [entry for entry in self.log_mgr.export_buffer if matches_category(entry, scope)]

        if not logs:
            label = "logs" if scope == "all" else f"{scope} entries"
            QtWidgets.QMessageBox.information(self, "Export", f"No {label} captured yet.")
            return

        model = self._device_details.model if self._device_details else "device"
        target = self._target_package or "full_device"
        suffix = "" if scope == "all" else f"_{scope}"
        default_name = LogExporter.generate_default_filename(model, target + suffix)

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export logs", default_name, "Log files (*.log);;Text files (*.txt)"
        )
        if not path:
            return

        errors, warnings, crashes = self._counts
        try:
            count = LogExporter.export_to_file(
                filepath=path,
                logs=logs,
                details=self._device_details,
                mode=self.log_mgr.mode_label,
                start_time=self.log_mgr.start_time,
                error_count=errors,
                warning_count=warnings,
                crash_count=crashes,
                filter_label=None if scope == "all" else scope.title(),
            )
            QtWidgets.QMessageBox.information(
                self, "Logs saved", f"{count} entries written to:\n{path}"
            )
        except Exception as exc:  # noqa: BLE001 - surface to the user
            QtWidgets.QMessageBox.critical(self, "Save failed", str(exc))
