"""Evidence Management & Export Panel for SUSCRCPY Workstation.

Displays the active session's evidence files (screenshots, recordings, logs, notes),
generates cryptographic SHA-256 integrity manifests, produces professional HTML reports,
and allows instant opening of the evidence repository.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.evidence_manager import EvidenceManager
from core.notes_manager import NotesManager
from core.report_generator import ReportGenerator
from core.session_manager import SessionManager

logger = logging.getLogger("suscrcpy.ui.evidence_panel")


class EvidencePanel(QtWidgets.QWidget):
    """Panel providing an evidence file browser, hash verification, and report generator."""

    def __init__(
        self,
        evidence_manager: EvidenceManager,
        session_manager: SessionManager,
        notes_manager: NotesManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.evidence_mgr = evidence_manager
        self.session_mgr = session_manager
        self.notes_mgr = notes_manager

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Toolbar
        tb_layout = QtWidgets.QHBoxLayout()
        tb_layout.setSpacing(8)

        self.open_folder_btn = QtWidgets.QPushButton("📁 Open Evidence Folder")
        self.open_folder_btn.setStyleSheet("padding: 5px 12px; font-weight: 600;")
        tb_layout.addWidget(self.open_folder_btn)

        self.gen_report_btn = QtWidgets.QPushButton("📊 Generate HTML Report")
        self.gen_report_btn.setStyleSheet("background-color: #3B82F6; color: white; padding: 5px 14px; font-weight: 600; border-radius: 4px;")
        tb_layout.addWidget(self.gen_report_btn)

        self.view_report_btn = QtWidgets.QPushButton("🌐 View Report")
        self.view_report_btn.setEnabled(False)
        tb_layout.addWidget(self.view_report_btn)

        self.manifest_btn = QtWidgets.QPushButton("🔒 Generate Manifest")
        tb_layout.addWidget(self.manifest_btn)

        tb_layout.addStretch()

        self.refresh_btn = QtWidgets.QPushButton("↻ Refresh")
        tb_layout.addWidget(self.refresh_btn)

        layout.addLayout(tb_layout)

        # Splitter between evidence list and preview
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Evidence Tree
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Evidence File", "Size", "SHA-256"])
        self.tree.setStyleSheet("QTreeWidget { background-color: #0F141C; border: 1px solid #263345; font-size: 12px; }")
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.tree)

        # Preview Area
        self.preview_card = QtWidgets.QFrame()
        self.preview_card.setStyleSheet("QFrame { background-color: #18202C; border: 1px solid #263345; border-radius: 4px; padding: 10px; }")
        pc_layout = QtWidgets.QVBoxLayout(self.preview_card)
        pc_layout.setContentsMargins(4, 4, 4, 4)

        self.preview_title = QtWidgets.QLabel("Evidence Preview")
        self.preview_title.setStyleSheet("font-weight: 600; color: #FFF; font-size: 12px;")
        pc_layout.addWidget(self.preview_title)

        self.preview_img = QtWidgets.QLabel("No item selected.")
        self.preview_img.setStyleSheet("color: #8DA2BC; font-size: 11px;")
        self.preview_img.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pc_layout.addWidget(self.preview_img, 1)

        splitter.addWidget(self.preview_card)
        splitter.setSizes([450, 350])
        layout.addWidget(splitter, 1)

        # Status / Path Readout
        self.path_lbl = QtWidgets.QLabel("Session Evidence Directory: None")
        self.path_lbl.setStyleSheet("color: #8DA2BC; font-size: 11px;")
        layout.addWidget(self.path_lbl)

    def _connect_signals(self) -> None:
        self.open_folder_btn.clicked.connect(self._open_evidence_folder)
        self.gen_report_btn.clicked.connect(self.generate_report)
        self.view_report_btn.clicked.connect(self._view_report)
        self.manifest_btn.clicked.connect(self._generate_manifest)
        self.refresh_btn.clicked.connect(self.refresh_evidence_tree)
        self.tree.itemSelectionChanged.connect(self._on_item_selected)

        self.session_mgr.session_state_changed.connect(lambda _: self.refresh_evidence_tree())

    def refresh_evidence_tree(self) -> None:
        """Scan active session folder and populate tree."""
        self.tree.clear()
        session_dir = self.evidence_mgr.current_session_dir
        if not session_dir or not session_dir.exists():
            self.path_lbl.setText("Session Evidence Directory: None (No active session)")
            self.view_report_btn.setEnabled(False)
            return

        self.path_lbl.setText(f"Session Evidence Directory: {session_dir}")

        # Check if report exists
        report_file = session_dir / "reports" / "session_report.html"
        self.view_report_btn.setEnabled(report_file.exists())

        # Categories to show
        subdirs = ["screenshots", "recordings", "logs", "notes", "events", "reports", "exports"]
        for sub in subdirs:
            folder = session_dir / sub
            if not folder.exists():
                continue
            parent_item = QtWidgets.QTreeWidgetItem(self.tree, [sub.capitalize(), "", ""])
            parent_item.setExpanded(True)
            for f in sorted(folder.iterdir()):
                if f.is_file():
                    size_kb = f.stat().st_size / 1024
                    size_str = f"{size_kb:.1f} KB" if size_kb >= 1 else f"{f.stat().st_size} B"
                    child = QtWidgets.QTreeWidgetItem(parent_item, [f.name, size_str, ""])
                    child.setData(0, QtCore.Qt.ItemDataRole.UserRole, str(f))

    def _on_item_selected(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            self.preview_title.setText("Evidence Preview")
            self.preview_img.setText("No item selected.")
            self.preview_img.setPixmap(QtGui.QPixmap())
            return

        item = items[0]
        filepath_str = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not filepath_str:
            self.preview_title.setText(item.text(0))
            self.preview_img.setText("Folder container.")
            self.preview_img.setPixmap(QtGui.QPixmap())
            return

        path = Path(filepath_str)
        self.preview_title.setText(path.name)

        if path.suffix.lower() in (".png", ".jpg", ".jpeg"):
            pm = QtGui.QPixmap(str(path))
            scaled = pm.scaled(
                self.preview_img.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_img.setPixmap(scaled)
        elif path.suffix.lower() in (".log", ".json", ".html", ".txt"):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(500)
                self.preview_img.setPixmap(QtGui.QPixmap())
                self.preview_img.setText(f"{content}...")
            except Exception:
                self.preview_img.setText(f"File size: {path.stat().st_size} bytes")
        else:
            self.preview_img.setPixmap(QtGui.QPixmap())
            self.preview_img.setText(f"Media asset: {path.suffix.upper()}\nSize: {path.stat().st_size} bytes")

    def _open_evidence_folder(self) -> None:
        session_dir = self.evidence_mgr.current_session_dir or self.evidence_mgr.base_dir
        if session_dir.exists():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(session_dir)))

    def generate_report(self) -> None:
        """Compile and write HTML report for the active session."""
        session = self.session_mgr.active_session
        session_dir = self.evidence_mgr.current_session_dir
        if not session or not session_dir:
            QtWidgets.QMessageBox.warning(self, "No Active Session", "Please create or select a testing session first.")
            return

        report_path = session_dir / "reports" / "session_report.html"
        
        # Pull screenshots, timeline, observations
        obs = self.notes_mgr.observations
        manifest_path, manifest_items = self.evidence_mgr.generate_manifest()

        ReportGenerator.generate_html_report(
            session=session,
            output_path=report_path,
            observations=obs,
            manifest_items=manifest_items,
            embed_images=False,
        )

        self.refresh_evidence_tree()
        QtWidgets.QMessageBox.information(
            self, "Report Generated",
            f"HTML Test Session Report successfully generated at:\n{report_path}"
        )

    def _view_report(self) -> None:
        session_dir = self.evidence_mgr.current_session_dir
        if not session_dir:
            return
        report_file = session_dir / "reports" / "session_report.html"
        if report_file.exists():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(report_file)))

    def _generate_manifest(self) -> None:
        session_dir = self.evidence_mgr.current_session_dir
        if not session_dir:
            QtWidgets.QMessageBox.warning(self, "No Session", "No active session directory.")
            return
        try:
            m_path, items = self.evidence_mgr.generate_manifest()
            self.refresh_evidence_tree()
            QtWidgets.QMessageBox.information(
                self, "Manifest Generated",
                f"Cryptographic SHA-256 Manifest generated for {len(items)} evidence files at:\n{m_path.name}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Manifest Error", f"Failed to generate manifest: {e}")
