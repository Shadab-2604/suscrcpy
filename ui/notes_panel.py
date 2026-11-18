"""Test Observations & Defect Notes Panel for SUSCRCPY Workstation.

Allows testers to log bugs and observations directly during live app interaction,
link them to captured screenshots and error logs, and assign severity/category.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.notes_manager import CATEGORIES, SEVERITIES, NotesManager, TestObservation
from core.session_manager import SessionManager

logger = logging.getLogger("suscrcpy.ui.notes_panel")


class ObservationEditDialog(QtWidgets.QDialog):
    """Dialog to create or edit a structured test observation."""

    def __init__(
        self,
        available_screenshots: List[str],
        observation: Optional[TestObservation] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.obs = observation
        self.available_screenshots = available_screenshots
        self.setWindowTitle("Edit Observation" if observation else "Log New Test Observation")
        self.resize(560, 520)
        self.setStyleSheet("background-color: #12161F; color: #EEEEEE;")

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Form layout
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        self.title_input = QtWidgets.QLineEdit()
        self.title_input.setPlaceholderText("Brief defect summary (e.g. Login crash on empty password)")
        form.addRow("Title *:", self.title_input)

        row_meta = QtWidgets.QHBoxLayout()
        self.severity_combo = QtWidgets.QComboBox()
        self.severity_combo.addItems(SEVERITIES)
        self.severity_combo.setCurrentText("Medium")
        row_meta.addWidget(self.severity_combo)

        row_meta.addWidget(QtWidgets.QLabel("Category:"))
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItems(CATEGORIES)
        self.category_combo.setCurrentText("Functional")
        row_meta.addWidget(self.category_combo)
        form.addRow("Severity:", row_meta)

        self.desc_input = QtWidgets.QPlainTextEdit()
        self.desc_input.setPlaceholderText("Detailed description of the observation or steps to reproduce...")
        self.desc_input.setMaximumHeight(90)
        form.addRow("Description:", self.desc_input)

        self.exp_input = QtWidgets.QLineEdit()
        self.exp_input.setPlaceholderText("What was supposed to happen?")
        form.addRow("Expected:", self.exp_input)

        self.act_input = QtWidgets.QLineEdit()
        self.act_input.setPlaceholderText("What actually happened?")
        form.addRow("Actual:", self.act_input)

        # Screenshot attachment
        self.shot_combo = QtWidgets.QComboBox()
        self.shot_combo.addItem("None", None)
        for s in self.available_screenshots:
            self.shot_combo.addItem(Path(s).name, s)
        form.addRow("Attach Screenshot:", self.shot_combo)

        layout.addLayout(form)

        # Populate if editing
        if self.obs:
            self.title_input.setText(self.obs.title)
            self.severity_combo.setCurrentText(self.obs.severity)
            self.category_combo.setCurrentText(self.obs.category)
            self.desc_input.setPlainText(self.obs.description)
            self.exp_input.setText(self.obs.expected_result)
            self.act_input.setText(self.obs.actual_result)
            if self.obs.screenshot_path:
                idx = self.shot_combo.findData(self.obs.screenshot_path)
                if idx >= 0:
                    self.shot_combo.setCurrentIndex(idx)

        # Buttons
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.addStretch()
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("Save Observation")
        self.save_btn.setStyleSheet("background-color: #3B82F6; color: white; padding: 6px 16px; font-weight: 600; border-radius: 4px;")
        btn_box.addWidget(self.cancel_btn)
        btn_box.addWidget(self.save_btn)
        layout.addLayout(btn_box)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._on_save)

    def _on_save(self) -> None:
        if not self.title_input.text().strip():
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Title is required.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "title": self.title_input.text().strip(),
            "severity": self.severity_combo.currentText(),
            "category": self.category_combo.currentText(),
            "description": self.desc_input.toPlainText().strip(),
            "expected_result": self.exp_input.text().strip(),
            "actual_result": self.act_input.text().strip(),
            "screenshot_path": self.shot_combo.currentData(),
        }


class NotesPanel(QtWidgets.QWidget):
    """Panel containing the list of test observations and bug logging controls."""

    def __init__(
        self,
        notes_manager: NotesManager,
        session_manager: SessionManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.notes_mgr = notes_manager
        self.session_mgr = session_manager
        self._available_screenshots: List[str] = []

        self._build_ui()
        self._connect_signals()

    def set_available_screenshots(self, shots: List[str]) -> None:
        self._available_screenshots = shots

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header controls
        ctrl_layout = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("+ Log Observation")
        self.add_btn.setStyleSheet("background-color: #3B82F6; color: white; font-weight: 600; padding: 5px 12px; border-radius: 4px;")
        ctrl_layout.addWidget(self.add_btn)

        self.edit_btn = QtWidgets.QPushButton("Edit")
        self.edit_btn.setEnabled(False)
        ctrl_layout.addWidget(self.edit_btn)

        self.del_btn = QtWidgets.QPushButton("Delete")
        self.del_btn.setEnabled(False)
        ctrl_layout.addWidget(self.del_btn)

        ctrl_layout.addStretch()

        filter_lbl = QtWidgets.QLabel("Filter:")
        filter_lbl.setStyleSheet("color: #8DA2BC; font-size: 11px;")
        ctrl_layout.addWidget(filter_lbl)

        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems(["All Severities"] + SEVERITIES)
        ctrl_layout.addWidget(self.filter_combo)

        layout.addLayout(ctrl_layout)

        # Table of Observations
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Severity", "Category", "Title", "Screenshot"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet("QTableWidget { background-color: #0F141C; border: 1px solid #263345; }")
        layout.addWidget(self.table, 1)

        # Detail preview card
        self.detail_card = QtWidgets.QFrame()
        self.detail_card.setStyleSheet("QFrame { background-color: #18202C; border: 1px solid #263345; border-radius: 4px; padding: 8px; }")
        det_layout = QtWidgets.QVBoxLayout(self.detail_card)
        det_layout.setContentsMargins(8, 8, 8, 8)
        self.detail_title = QtWidgets.QLabel("Select an observation to view details.")
        self.detail_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #FFF;")
        self.detail_text = QtWidgets.QLabel("")
        self.detail_text.setStyleSheet("color: #8DA2BC; font-size: 11px;")
        self.detail_text.setWordWrap(True)
        det_layout.addWidget(self.detail_title)
        det_layout.addWidget(self.detail_text)
        layout.addWidget(self.detail_card)

    def _connect_signals(self) -> None:
        self.add_btn.clicked.connect(self.prompt_add_observation)
        self.edit_btn.clicked.connect(self._on_edit)
        self.del_btn.clicked.connect(self._on_delete)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.filter_combo.currentTextChanged.connect(self._refresh_table)

        self.notes_mgr.observation_added.connect(lambda _: self._refresh_table())
        self.notes_mgr.observation_updated.connect(lambda _: self._refresh_table())
        self.notes_mgr.observation_deleted.connect(lambda _: self._refresh_table())

    def prompt_add_observation(self) -> None:
        """Open observation creation dialog."""
        dlg = ObservationEditDialog(self._available_screenshots, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            session = self.session_mgr.active_session
            session_id = session.session_id if session else None
            pkg = session.target_package if session else None
            self.notes_mgr.add_observation(
                title=data["title"],
                description=data["description"],
                severity=data["severity"],
                category=data["category"],
                expected_result=data["expected_result"],
                actual_result=data["actual_result"],
                session_id=session_id,
                package_name=pkg,
                screenshot_path=data["screenshot_path"],
            )

    def _on_edit(self) -> None:
        selected = self._get_selected_observation()
        if not selected:
            return
        dlg = ObservationEditDialog(self._available_screenshots, observation=selected, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            self.notes_mgr.update_observation(
                selected.obs_id,
                title=data["title"],
                description=data["description"],
                severity=data["severity"],
                category=data["category"],
                expected_result=data["expected_result"],
                actual_result=data["actual_result"],
                screenshot_path=data["screenshot_path"],
            )

    def _on_delete(self) -> None:
        selected = self._get_selected_observation()
        if not selected:
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete observation '{selected.title}'?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.notes_mgr.delete_observation(selected.obs_id)

    def _get_selected_observation(self) -> Optional[TestObservation]:
        row = self.table.currentRow()
        if row < 0:
            return None
        obs_id_item = self.table.item(row, 0)
        if not obs_id_item:
            return None
        obs_id = obs_id_item.text()
        for o in self.notes_mgr.observations:
            if o.obs_id == obs_id:
                return o
        return None

    def _on_selection_changed(self) -> None:
        obs = self._get_selected_observation()
        has_sel = obs is not None
        self.edit_btn.setEnabled(has_sel)
        self.del_btn.setEnabled(has_sel)

        if obs:
            self.detail_title.setText(f"[{obs.severity}] {obs.title} ({obs.category})")
            desc = obs.description or "No description provided."
            exp_act = ""
            if obs.expected_result or obs.actual_result:
                exp_act = f"\nExpected: {obs.expected_result}\nActual: {obs.actual_result}"
            shot = f"\nAttachment: {Path(obs.screenshot_path).name}" if obs.screenshot_path else ""
            self.detail_text.setText(f"{desc}{exp_act}{shot}")
        else:
            self.detail_title.setText("Select an observation to view details.")
            self.detail_text.setText("")

    def _refresh_table(self) -> None:
        crit_filter = self.filter_combo.currentText()
        all_obs = self.notes_mgr.observations

        self.table.setRowCount(0)
        for obs in all_obs:
            if crit_filter != "All Severities" and obs.severity != crit_filter:
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            id_item = QtWidgets.QTableWidgetItem(obs.obs_id)
            sev_item = QtWidgets.QTableWidgetItem(obs.severity)
            # Color code severity
            if obs.severity == "Critical":
                sev_item.setForeground(QtGui.QColor("#F87171"))
            elif obs.severity == "High":
                sev_item.setForeground(QtGui.QColor("#FBBF24"))
            elif obs.severity == "Medium":
                sev_item.setForeground(QtGui.QColor("#93C5FD"))
            elif obs.severity == "Low":
                sev_item.setForeground(QtGui.QColor("#34D399"))

            cat_item = QtWidgets.QTableWidgetItem(obs.category)
            title_item = QtWidgets.QTableWidgetItem(obs.title)
            shot_item = QtWidgets.QTableWidgetItem(Path(obs.screenshot_path).name if obs.screenshot_path else "—")

            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, sev_item)
            self.table.setItem(row, 2, cat_item)
            self.table.setItem(row, 3, title_item)
            self.table.setItem(row, 4, shot_item)
