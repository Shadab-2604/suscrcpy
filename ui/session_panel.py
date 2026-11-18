"""Testing Session Management Panel for SUSCRCPY Workstation.

Provides session creation, lifecycle controls (Start, Pause, Resume, End),
live diagnostics counters, and the chronological event timeline.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.event_manager import EventManager, TimelineEvent
from core.session_manager import TEST_TYPES, SessionManager, SessionMetadata, SessionStatus

logger = logging.getLogger("suscrcpy.ui.session_panel")


class CreateSessionDialog(QtWidgets.QDialog):
    """Modal dialog to configure and initiate a new testing session."""

    def __init__(
        self,
        suggested_id: str,
        device_details: dict,
        target_app: Optional[dict] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.device_details = device_details
        self.target_app = target_app or {}

        self.setWindowTitle(f"Start Testing Session — {suggested_id}")
        self.resize(540, 500)
        self.setStyleSheet("background-color: #12161F; color: #EEEEEE;")

        self._build_ui(suggested_id)

    def _build_ui(self, suggested_id: str) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        id_lbl = QtWidgets.QLabel(suggested_id)
        id_lbl.setStyleSheet("font-weight: 700; color: #60A5FA;")
        form.addRow("Session ID:", id_lbl)

        self.project_input = QtWidgets.QLineEdit()
        self.project_input.setText("AndroidQA")
        form.addRow("Project Name *:", self.project_input)

        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setText(f"Session {suggested_id}")
        form.addRow("Session Name *:", self.name_input)

        self.test_type_combo = QtWidgets.QComboBox()
        self.test_type_combo.addItems(TEST_TYPES)
        self.test_type_combo.setCurrentText("Functional Testing")
        form.addRow("Test Type:", self.test_type_combo)

        self.tester_input = QtWidgets.QLineEdit()
        self.tester_input.setPlaceholderText("Tester name or identifier")
        form.addRow("Tester:", self.tester_input)

        # Context read-outs
        dev_str = f"{self.device_details.get('model', 'Unknown')} ({self.device_details.get('serial', 'N/A')})"
        form.addRow("Connected Device:", QtWidgets.QLabel(dev_str))

        app_str = f"{self.target_app.get('app_name', 'Full Device')} ({self.target_app.get('package_name', 'All Packages')})"
        form.addRow("Target Application:", QtWidgets.QLabel(app_str))

        self.notes_input = QtWidgets.QPlainTextEdit()
        self.notes_input.setPlaceholderText("Initial test plan objectives, scope, or environment notes...")
        self.notes_input.setMaximumHeight(80)
        form.addRow("Tester Notes:", self.notes_input)

        layout.addLayout(form)

        btn_box = QtWidgets.QHBoxLayout()
        btn_box.addStretch()
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.start_btn = QtWidgets.QPushButton("🚀 Start Session")
        self.start_btn.setStyleSheet("background-color: #3B82F6; color: white; padding: 6px 18px; font-weight: 600; border-radius: 4px;")
        btn_box.addWidget(self.cancel_btn)
        btn_box.addWidget(self.start_btn)
        layout.addLayout(btn_box)

        self.cancel_btn.clicked.connect(self.reject)
        self.start_btn.clicked.connect(self._on_start)

    def _on_start(self) -> None:
        if not self.project_input.text().strip():
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Project Name is required.")
            return
        if not self.name_input.text().strip():
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Session Name is required.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "project_name": self.project_input.text().strip(),
            "session_name": self.name_input.text().strip(),
            "test_type": self.test_type_combo.currentText(),
            "tester_name": self.tester_input.text().strip(),
            "tester_notes": self.notes_input.toPlainText().strip(),
        }


class SessionPanel(QtWidgets.QWidget):
    """Panel managing active testing session, stats, and chronological timeline."""

    def __init__(
        self,
        session_manager: SessionManager,
        event_manager: EventManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.session_mgr = session_manager
        self.event_mgr = event_manager

        self._active_device_details: dict = {}
        self._active_target_app: Optional[dict] = None

        self._build_ui()
        self._connect_signals()

    def set_device_context(self, details: dict) -> None:
        self._active_device_details = details

    def set_app_context(self, app_dict: Optional[dict]) -> None:
        self._active_target_app = app_dict

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Active Session Header Card
        self.card = QtWidgets.QFrame()
        self.card.setStyleSheet("QFrame { background-color: #18202C; border: 1px solid #263345; border-radius: 6px; padding: 12px; }")
        c_layout = QtWidgets.QVBoxLayout(self.card)
        c_layout.setContentsMargins(8, 8, 8, 8)

        top_row = QtWidgets.QHBoxLayout()
        self.status_chip = QtWidgets.QLabel("NO ACTIVE SESSION")
        self.status_chip.setStyleSheet("background: rgba(141, 162, 188, 0.2); color: #8DA2BC; border: 1px solid #263345; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;")
        self.session_title = QtWidgets.QLabel("Start a session to bind logs, screenshots, and defects.")
        self.session_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #FFF;")

        top_row.addWidget(self.status_chip)
        top_row.addWidget(self.session_title, 1)
        c_layout.addLayout(top_row)

        self.session_info = QtWidgets.QLabel("")
        self.session_info.setStyleSheet("color: #8DA2BC; font-size: 11px; margin-top: 4px;")
        c_layout.addWidget(self.session_info)

        # Controls Row
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)

        self.new_btn = QtWidgets.QPushButton("+ New Session")
        self.new_btn.setStyleSheet("background-color: #3B82F6; color: white; font-weight: 600; padding: 5px 12px; border-radius: 4px;")
        btn_row.addWidget(self.new_btn)

        self.pause_btn = QtWidgets.QPushButton("⏸ Pause")
        self.pause_btn.setEnabled(False)
        btn_row.addWidget(self.pause_btn)

        self.end_btn = QtWidgets.QPushButton("⏹ Conclude Session")
        self.end_btn.setEnabled(False)
        self.end_btn.setStyleSheet("background-color: #EF4444; color: white; font-weight: 600; padding: 5px 12px; border-radius: 4px;")
        btn_row.addWidget(self.end_btn)

        btn_row.addStretch()
        c_layout.addLayout(btn_row)

        layout.addWidget(self.card)

        # Live Metrics
        metrics_box = QtWidgets.QHBoxLayout()
        self.m_crashes = self._create_metric("0", "CRASHES", "#EF4444")
        self.m_errors = self._create_metric("0", "ERRORS", "#F59E0B")
        self.m_obs = self._create_metric("0", "NOTES", "#3B82F6")
        self.m_shots = self._create_metric("0", "SHOTS", "#10B981")
        self.m_recs = self._create_metric("0", "RECS", "#06B6D4")

        metrics_box.addWidget(self.m_crashes)
        metrics_box.addWidget(self.m_errors)
        metrics_box.addWidget(self.m_obs)
        metrics_box.addWidget(self.m_shots)
        metrics_box.addWidget(self.m_recs)
        layout.addLayout(metrics_box)

        # Chronological Event Timeline
        tl_grp = QtWidgets.QGroupBox("Session Event Timeline")
        tl_grp.setStyleSheet("QGroupBox { font-weight: 600; font-size: 12px; color: #FFF; border: 1px solid #263345; border-radius: 6px; margin-top: 6px; padding: 10px; }")
        tl_layout = QtWidgets.QVBoxLayout(tl_grp)

        self.tl_list = QtWidgets.QListWidget()
        self.tl_list.setStyleSheet("QListWidget { background-color: #0F141C; border: 1px solid #263345; font-size: 12px; }")
        tl_layout.addWidget(self.tl_list)

        layout.addWidget(tl_grp, 1)

    def _create_metric(self, num: str, label: str, color: str) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setStyleSheet("QFrame { background-color: #18202C; border: 1px solid #263345; border-radius: 4px; padding: 8px; }")
        v = QtWidgets.QVBoxLayout(frame)
        v.setContentsMargins(4, 4, 4, 4)
        v.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        num_lbl = QtWidgets.QLabel(num)
        num_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {color};")
        num_lbl.setObjectName("num")
        txt_lbl = QtWidgets.QLabel(label)
        txt_lbl.setStyleSheet("font-size: 9px; font-weight: 600; color: #8DA2BC;")
        v.addWidget(num_lbl, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        v.addWidget(txt_lbl, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        return frame

    def _connect_signals(self) -> None:
        self.new_btn.clicked.connect(self.prompt_create_session)
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.end_btn.clicked.connect(self._on_end_session)

        self.session_mgr.session_state_changed.connect(self._update_session_view)
        self.event_mgr.event_recorded.connect(self._on_event_recorded)
        self.event_mgr.timeline_cleared.connect(self.tl_list.clear)

    def prompt_create_session(self) -> None:
        """Display session creation dialog."""
        suggested_id = self.session_mgr.generate_session_id()
        dlg = CreateSessionDialog(suggested_id, self._active_device_details, self._active_target_app, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            dev = self._active_device_details
            app = self._active_target_app or {}
            meta = self.session_mgr.create_session(
                session_name=data["session_name"],
                project_name=data["project_name"],
                test_type=data["test_type"],
                tester_name=data["tester_name"],
                tester_notes=data["tester_notes"],
                device_serial=dev.get("serial", ""),
                device_model=dev.get("model", ""),
                device_manufacturer=dev.get("manufacturer", ""),
                android_version=dev.get("android_version", ""),
                sdk_version=dev.get("sdk_level", ""),
                screen_dimensions=dev.get("physical_resolution", (0, 0)),
                display_density=dev.get("density"),
                target_app_name=app.get("app_name", ""),
                target_package=app.get("package_name", ""),
                app_version=app.get("version_name", ""),
                app_version_code=app.get("version_code", ""),
            )
            self.session_mgr.start_session()
            self.event_mgr.clear()
            self.event_mgr.record_event(
                category="session",
                action="started",
                description=f"Testing session {meta.session_id} started ({meta.test_type})",
                session_id=meta.session_id,
                device_serial=meta.device_serial,
                package_name=meta.target_package,
            )

    def _toggle_pause(self) -> None:
        s = self.session_mgr.active_session
        if not s:
            return
        if s.status == SessionStatus.RUNNING.value:
            self.session_mgr.pause_session()
            self.event_mgr.record_event("session", "paused", f"Session {s.session_id} paused", session_id=s.session_id)
        elif s.status == SessionStatus.PAUSED.value:
            self.session_mgr.resume_session()
            self.event_mgr.record_event("session", "resumed", f"Session {s.session_id} resumed", session_id=s.session_id)

    def _on_end_session(self) -> None:
        s = self.session_mgr.active_session
        if not s:
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Conclude Session",
            f"Are you sure you want to conclude session '{s.session_id}'?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.event_mgr.record_event("session", "completed", f"Session {s.session_id} completed", session_id=s.session_id)
            self.session_mgr.end_session()

    def _update_session_view(self, meta: Optional[SessionMetadata]) -> None:
        if not meta:
            self.status_chip.setText("NO ACTIVE SESSION")
            self.status_chip.setStyleSheet("background: rgba(141, 162, 188, 0.2); color: #8DA2BC; border: 1px solid #263345; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;")
            self.session_title.setText("Start a session to bind logs, screenshots, and defects.")
            self.session_info.setText("")
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("⏸ Pause")
            self.end_btn.setEnabled(False)
            return

        is_running = meta.status == SessionStatus.RUNNING.value
        is_paused = meta.status == SessionStatus.PAUSED.value

        self.status_chip.setText(meta.status.upper())
        if is_running:
            self.status_chip.setStyleSheet("background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid #10B981; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;")
            self.pause_btn.setText("⏸ Pause")
            self.pause_btn.setEnabled(True)
            self.end_btn.setEnabled(True)
        elif is_paused:
            self.status_chip.setStyleSheet("background: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid #F59E0B; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;")
            self.pause_btn.setText("▶ Resume")
            self.pause_btn.setEnabled(True)
            self.end_btn.setEnabled(True)
        else:
            self.status_chip.setStyleSheet("background: rgba(59, 130, 246, 0.2); color: #93C5FD; border: 1px solid #3B82F6; padding: 3px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;")
            self.pause_btn.setEnabled(False)
            self.end_btn.setEnabled(False)

        self.session_title.setText(f"{meta.session_id}: {meta.session_name} ({meta.test_type})")
        app_desc = meta.target_package or "Full Device"
        self.session_info.setText(f"Target: {app_desc} | Device: {meta.device_model} ({meta.device_serial}) | Started: {meta.start_time[:19]}")

    def update_metrics(self, crashes: int, errors: int, obs: int, shots: int, recs: int) -> None:
        self.m_crashes.findChild(QtWidgets.QLabel, "num").setText(str(crashes))
        self.m_errors.findChild(QtWidgets.QLabel, "num").setText(str(errors))
        self.m_obs.findChild(QtWidgets.QLabel, "num").setText(str(obs))
        self.m_shots.findChild(QtWidgets.QLabel, "num").setText(str(shots))
        self.m_recs.findChild(QtWidgets.QLabel, "num").setText(str(recs))

    def _on_event_recorded(self, ev: TimelineEvent) -> None:
        time_str = ev.timestamp[11:19]
        item = QtWidgets.QListWidgetItem(f"[{time_str}] [{ev.category.upper()}] {ev.description}")
        if ev.category == "crash":
            item.setForeground(QtGui.QColor("#F87171"))
        elif ev.category in ("error", "warning"):
            item.setForeground(QtGui.QColor("#FBBF24"))
        elif ev.category == "capture":
            item.setForeground(QtGui.QColor("#34D399"))
        elif ev.category == "session":
            item.setForeground(QtGui.QColor("#60A5FA"))
        self.tl_list.addItem(item)
        self.tl_list.scrollToBottom()
