"""Embedded Live Android Screen View for SUSCRCPY.

Hosts the embedded native scrcpy display window inside the left panel of the interface,
handling container resizing, interaction forwarding, and graceful fallbacks.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.scrcpy_manager import ScrcpyManager
from platform import get_window_embedder
from platform.linux_wayland import WaylandHelper

logger = logging.getLogger("suscrcpy.ui.screen_view")


class ScreenView(QtWidgets.QWidget):
    """Left-side container hosting the live embedded scrcpy screen and testing toolbar."""

    embedding_failed = QtCore.Signal(str)
    screenshot_requested = QtCore.Signal()
    recording_toggle_requested = QtCore.Signal()
    quick_note_requested = QtCore.Signal()
    quality_changed = QtCore.Signal(str)
    fullscreen_toggled = QtCore.Signal(bool)

    def __init__(
        self,
        scrcpy_manager: ScrcpyManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.scrcpy_mgr = scrcpy_manager
        self._embedder = get_window_embedder()
        self._embedded_container: Optional[QtWidgets.QWidget] = None
        self._window_id: Optional[int] = None
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._check_and_embed)
        self._pending_title: Optional[str] = None
        self._pending_pid: Optional[int] = None
        self._poll_attempts = 0
        self._is_fullscreen = False

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Quick Testing Toolbar (Top of Mirror Container)
        self.toolbar = QtWidgets.QFrame()
        self.toolbar.setStyleSheet("QFrame { background-color: #12161F; border-bottom: 1px solid #263345; padding: 4px; }")
        tb_layout = QtWidgets.QHBoxLayout(self.toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(6)

        # Screenshot Button
        self.shot_btn = QtWidgets.QPushButton("📸 Shot")
        self.shot_btn.setToolTip("Capture Android Screen (Ctrl+Shift+S)")
        self.shot_btn.setStyleSheet("padding: 3px 8px; font-size: 11px; font-weight: 600;")
        self.shot_btn.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self.shot_btn.clicked.connect(self.screenshot_requested)
        tb_layout.addWidget(self.shot_btn)

        # Recording Toggle Button
        self.rec_btn = QtWidgets.QPushButton("⏺ Rec")
        self.rec_btn.setToolTip("Start/Stop Device Screen Recording (Ctrl+Shift+R)")
        self.rec_btn.setStyleSheet("padding: 3px 8px; font-size: 11px; font-weight: 600; color: #EF4444;")
        self.rec_btn.setShortcut(QtGui.QKeySequence("Ctrl+Shift+R"))
        self.rec_btn.clicked.connect(self.recording_toggle_requested)
        tb_layout.addWidget(self.rec_btn)

        self.rec_timer_lbl = QtWidgets.QLabel("")
        self.rec_timer_lbl.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: 700; margin-left: 2px;")
        self.rec_timer_lbl.setVisible(False)
        tb_layout.addWidget(self.rec_timer_lbl)

        # Quick Note Button
        self.note_btn = QtWidgets.QPushButton("📝 Note")
        self.note_btn.setToolTip("Quickly log a test observation (Ctrl+Shift+O)")
        self.note_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.note_btn.setShortcut(QtGui.QKeySequence("Ctrl+Shift+O"))
        self.note_btn.clicked.connect(self.quick_note_requested)
        tb_layout.addWidget(self.note_btn)

        tb_layout.addStretch()

        # Quality Profile Dropdown
        q_lbl = QtWidgets.QLabel("Quality:")
        q_lbl.setStyleSheet("color: #8DA2BC; font-size: 10px;")
        tb_layout.addWidget(q_lbl)

        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItems(["Balanced (1080p)", "Performance (720p)", "High (Native)"])
        self.quality_combo.setStyleSheet("font-size: 10px; padding: 2px 4px;")
        self.quality_combo.currentTextChanged.connect(self._on_quality_changed)
        tb_layout.addWidget(self.quality_combo)

        # Fullscreen Toggle Button
        self.fs_btn = QtWidgets.QPushButton("⛶")
        self.fs_btn.setToolTip("Toggle Fullscreen Mirror")
        self.fs_btn.setStyleSheet("padding: 3px 6px; font-size: 11px;")
        self.fs_btn.clicked.connect(self._toggle_fullscreen)
        tb_layout.addWidget(self.fs_btn)

        self.main_layout.addWidget(self.toolbar)

        # Placeholder / Empty State Frame
        self.placeholder = QtWidgets.QFrame()
        self.placeholder.setStyleSheet(
            "QFrame { background-color: #101010; border: 1px solid #282828; border-radius: 4px; }"
        )
        pl_layout = QtWidgets.QVBoxLayout(self.placeholder)
        pl_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pl_layout.setSpacing(10)

        self.status_title = QtWidgets.QLabel("No Active Display Mirror")
        self.status_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #EEEEEE;")
        self.status_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pl_layout.addWidget(self.status_title)

        self.status_desc = QtWidgets.QLabel(
            "Connect an Android device with USB Debugging enabled.\n"
            "The live interactive screen will be embedded here."
        )
        self.status_desc.setStyleSheet("color: #777777; font-size: 11px; line-height: 1.4;")
        self.status_desc.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pl_layout.addWidget(self.status_desc)

        # Wayland Advisory Card (only visible if pure Wayland prevents embedding)
        self.wayland_banner = QtWidgets.QFrame()
        self.wayland_banner.setStyleSheet(
            "QFrame { background-color: #1C1C1C; border: 1px solid #333333; border-radius: 4px; padding: 8px; margin: 12px; }"
        )
        wb_layout = QtWidgets.QVBoxLayout(self.wayland_banner)
        wb_title = QtWidgets.QLabel("Wayland Display Notice")
        wb_title.setStyleSheet("font-weight: 600; color: #D9A441; font-size: 11px;")
        self.wb_text = QtWidgets.QLabel("")
        self.wb_text.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.wb_text.setWordWrap(True)
        wb_layout.addWidget(wb_title)
        wb_layout.addWidget(self.wb_text)
        self.wayland_banner.setVisible(False)
        pl_layout.addWidget(self.wayland_banner)

        self.main_layout.addWidget(self.placeholder)

    def _connect_signals(self) -> None:
        self.scrcpy_mgr.started.connect(self._on_scrcpy_started)
        self.scrcpy_mgr.stopped.connect(self._on_scrcpy_stopped)

    def _on_quality_changed(self, text: str) -> None:
        if "Performance" in text:
            self.quality_changed.emit("performance")
        elif "High" in text:
            self.quality_changed.emit("high")
        else:
            self.quality_changed.emit("balanced")

    def _toggle_fullscreen(self) -> None:
        self._is_fullscreen = not self._is_fullscreen
        self.fullscreen_toggled.emit(self._is_fullscreen)

    def set_recording_state(self, is_recording: bool, elapsed_seconds: int = 0) -> None:
        if is_recording:
            self.rec_btn.setText("⏹ Stop Rec")
            self.rec_btn.setStyleSheet("padding: 3px 8px; font-size: 11px; font-weight: 600; background-color: #EF4444; color: white; border-radius: 3px;")
            m = elapsed_seconds // 60
            s = elapsed_seconds % 60
            self.rec_timer_lbl.setText(f"● {m:02d}:{s:02d}")
            self.rec_timer_lbl.setVisible(True)
        else:
            self.rec_btn.setText("⏺ Rec")
            self.rec_btn.setStyleSheet("padding: 3px 8px; font-size: 11px; font-weight: 600; color: #EF4444;")
            self.rec_timer_lbl.setVisible(False)

    def _on_scrcpy_started(self, window_title: str) -> None:
        """Handle scrcpy startup and begin native window polling."""
        self._pending_title = window_title
        proc = self.scrcpy_mgr.current_proc
        self._pending_pid = proc.pid if proc else None
        self._poll_attempts = 0

        self.status_title.setText("Embedding Live Android Screen...")
        self.status_desc.setText(f"Synchronizing session: {window_title}")
        self.wayland_banner.setVisible(False)

        if not self._embedder:
            self._embedder = get_window_embedder()

        if self._embedder:
            self._poll_timer.start()
        else:
            diag = WaylandHelper.get_diagnostics()
            self.wayland_banner.setVisible(True)
            self.wb_text.setText(diag.guidance_message)
            self.status_title.setText("scrcpy Running (Companion Mode)")
            self.status_desc.setText("Display server restricted cross-process window reparenting.")

    def _check_and_embed(self) -> None:
        """Poll for foreign scrcpy window and embed once ready."""
        self._poll_attempts += 1
        if not self._pending_title or not self._embedder:
            self._poll_timer.stop()
            return

        wid = self._embedder.find_window(self._pending_title, self._pending_pid, timeout=0.1)
        if wid:
            self._poll_timer.stop()
            logger.info("Found native window 0x%x; embedding into container...", wid)
            self._window_id = wid
            self._embed_native_window(wid)
            return

        if self._poll_attempts > 60:  # 5 seconds
            self._poll_timer.stop()
            logger.warning("Scrcpy window embedding timed out; keeping external window.")
            self.status_title.setText("scrcpy Screen Active (External Window)")
            self.status_desc.setText("The mirroring session is active in its native window.")

    def _embed_native_window(self, window_id: int) -> None:
        """Reparent foreign window into this widget."""
        if not self._embedder:
            return

        container = self._embedder.embed_window(window_id, self)
        if container:
            self._embedded_container = container
            self.placeholder.setVisible(False)
            self.main_layout.addWidget(container)
            container.setVisible(True)
            container.setFocus()
            logger.info("Native window 0x%x embedded successfully.", window_id)
        else:
            self.placeholder.setVisible(True)
            self.status_title.setText("Window Embedding Unsupported")
            self.status_desc.setText("Foreign window could not be reparented in this session.")

    def _on_scrcpy_stopped(self, exit_code: int) -> None:
        """Clean up embedded container when scrcpy terminates."""
        self._poll_timer.stop()
        if self._embedded_container:
            self.main_layout.removeWidget(self._embedded_container)
            self._embedded_container.deleteLater()
            self._embedded_container = None

        self._window_id = None
        self._pending_title = None
        self._pending_pid = None

        self.placeholder.setVisible(True)
        self.status_title.setText("No Active Display Mirror")
        self.status_desc.setText("Select a device or resolution ratio to restart screen mirroring.")
        self.wayland_banner.setVisible(False)

    def reset_view(self) -> None:
        """Reset view to clean disconnected state."""
        self._on_scrcpy_stopped(0)
        self.status_title.setText("No Active Display Mirror")
        self.status_desc.setText("Connect an Android device with USB Debugging enabled.")
