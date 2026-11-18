"""Embedded Live Android Screen View for SUSCRCPY.

Hosts the embedded native scrcpy display window inside the left panel of the interface,
handling responsive ViewportCanvas letterboxing/pillarboxing with mathematical contain/fill/original
aspect ratio fitting, Sync HUD diagnostics, interaction forwarding, and graceful fallbacks.
"""
from __future__ import annotations

import logging
import math
from typing import Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from core.scrcpy_manager import ScrcpyManager
from platform import get_window_embedder
from platform.linux_wayland import WaylandHelper

logger = logging.getLogger("suscrcpy.ui.screen_view")


class ViewportCanvas(QtWidgets.QWidget):
    """Black canvas hosting the embedded scrcpy window with responsive letterbox/pillarbox fitting."""

    geometry_updated = QtCore.Signal(int, int, str)  # preview_w, preview_h, ratio_str

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("viewportCanvas")
        self.setStyleSheet("QWidget#viewportCanvas { background-color: #0A0A0A; }")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        self._embedded_container: Optional[QtWidgets.QWidget] = None
        self._target_w = 800
        self._target_h = 1280
        self._mode = "fit"  # "fit", "fill", or "original"

        # Debounced resize timer for butter-smooth splitter and window resizing
        self._resize_timer = QtCore.QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(10)
        self._resize_timer.timeout.connect(self._do_recalculate_geometry)

        # Centered placeholder frame when no scrcpy container is attached
        self.placeholder_layout = QtWidgets.QVBoxLayout(self)
        self.placeholder_layout.setContentsMargins(20, 20, 20, 20)
        self.placeholder_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.placeholder = QtWidgets.QFrame(self)
        self.placeholder.setStyleSheet(
            "QFrame { background-color: #12141A; border: 1px solid #232733; border-radius: 6px; padding: 16px; }"
        )
        pl_layout = QtWidgets.QVBoxLayout(self.placeholder)
        pl_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pl_layout.setSpacing(8)

        self.status_title = QtWidgets.QLabel("No Active Display Mirror")
        self.status_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #EEEEEE;")
        self.status_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pl_layout.addWidget(self.status_title)

        self.status_desc = QtWidgets.QLabel(
            "Connect an Android device with USB Debugging enabled.\n"
            "The live interactive screen will be embedded here."
        )
        self.status_desc.setStyleSheet("color: #7E8B9B; font-size: 11px; line-height: 1.4;")
        self.status_desc.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        pl_layout.addWidget(self.status_desc)

        # Wayland Advisory Card
        self.wayland_banner = QtWidgets.QFrame()
        self.wayland_banner.setStyleSheet(
            "QFrame { background-color: #1F1B12; border: 1px solid #634A1B; border-radius: 4px; padding: 8px; margin-top: 10px; }"
        )
        wb_layout = QtWidgets.QVBoxLayout(self.wayland_banner)
        wb_title = QtWidgets.QLabel("Wayland Display Notice")
        wb_title.setStyleSheet("font-weight: 600; color: #EAB308; font-size: 11px;")
        self.wb_text = QtWidgets.QLabel("")
        self.wb_text.setStyleSheet("color: #D1D5DB; font-size: 11px;")
        self.wb_text.setWordWrap(True)
        wb_layout.addWidget(wb_title)
        wb_layout.addWidget(self.wb_text)
        self.wayland_banner.setVisible(False)
        pl_layout.addWidget(self.wayland_banner)

        # Temporary Updating Display Overlay Badge
        self.updating_badge = QtWidgets.QFrame(self)
        self.updating_badge.setStyleSheet(
            "QFrame { background-color: rgba(18, 22, 31, 0.92); border: 1px solid #3B82F6; border-radius: 6px; padding: 8px 16px; }"
        )
        ub_layout = QtWidgets.QHBoxLayout(self.updating_badge)
        ub_layout.setContentsMargins(10, 6, 10, 6)
        ub_layout.setSpacing(8)
        self.ub_label = QtWidgets.QLabel("⟳ Updating display... Synchronizing stream")
        self.ub_label.setStyleSheet("color: #60A5FA; font-weight: 600; font-size: 12px;")
        ub_layout.addWidget(self.ub_label)
        self.updating_badge.setVisible(False)

        self.placeholder_layout.addWidget(self.placeholder)

    def attach_container(self, container: QtWidgets.QWidget) -> None:
        """Reparent and anchor external scrcpy container inside canvas."""
        self.placeholder.setVisible(False)
        self._embedded_container = container
        container.setParent(self)
        container.setVisible(True)
        self._do_recalculate_geometry()
        container.show()
        container.setFocus()

    def detach_container(self) -> None:
        """Remove scrcpy container and restore placeholder."""
        if self._embedded_container:
            self._embedded_container.setParent(None)
            self._embedded_container.deleteLater()
            self._embedded_container = None
        self.placeholder.setVisible(True)

    def set_target_dimensions(self, width: int, height: int) -> None:
        """Update stream/logical aspect ratio target and re-fit."""
        if width > 0 and height > 0:
            self._target_w = width
            self._target_h = height
            self.recalculate_geometry()

    def set_display_mode(self, mode: str) -> None:
        """Set scaling mode ('fit', 'fill', or 'original')."""
        self._mode = mode.lower()
        self.recalculate_geometry()

    def show_updating_overlay(self, show: bool = True, text: str = "⟳ Updating display...") -> None:
        """Display temporary status indicator during resolution changes."""
        self.ub_label.setText(text)
        self.updating_badge.setVisible(show)
        if show:
            self.updating_badge.raise_()
            self._position_overlay()

    def _position_overlay(self) -> None:
        if self.updating_badge.isVisible():
            bw = self.updating_badge.sizeHint().width()
            bh = self.updating_badge.sizeHint().height()
            bx = (self.width() - bw) // 2
            by = (self.height() - bh) // 2
            self.updating_badge.setGeometry(bx, by, bw, bh)

    def calculate_fitted_geometry(
        self,
        avail_w: int,
        avail_h: int,
        target_w: int,
        target_h: int,
    ) -> QtCore.QRect:
        """Calculate aspect-ratio-preserving rectangle using strict mathematical scaling.

        Let CW = avail_w, CH = avail_h, SW = target_w, SH = target_h.
        - FIT mode: scale = min(CW / SW, CH / SH)
        - FILL mode: scale = max(CW / SW, CH / SH)
        - ORIGINAL mode: scale = 1.0 (subject to available canvas bounds)
        """
        if avail_w <= 0 or avail_h <= 0 or target_w <= 0 or target_h <= 0:
            return QtCore.QRect(0, 0, max(1, avail_w), max(1, avail_h))

        cw, ch = float(avail_w), float(avail_h)
        sw, sh = float(target_w), float(target_h)

        if self._mode == "original":
            # 1:1 pixel mapping: render at actual source dimensions
            rendered_w = int(round(sw))
            rendered_h = int(round(sh))
            x = (avail_w - rendered_w) // 2
            y = (avail_h - rendered_h) // 2
            return QtCore.QRect(x, y, rendered_w, rendered_h)

        if self._mode == "fill":
            # FILL mode: scale = max(CW / SW, CH / SH) -> fills entire container, cropping excess
            scale = max(cw / sw, ch / sh)
            rendered_w = max(1, int(round(sw * scale)))
            rendered_h = max(1, int(round(sh * scale)))
            x = (avail_w - rendered_w) // 2
            y = (avail_h - rendered_h) // 2
            return QtCore.QRect(x, y, rendered_w, rendered_h)

        # FIT mode (default): scale = min(CW / SW, CH / SH) -> complete screen visible, letterbox/pillarbox
        scale = min(cw / sw, ch / sh)
        rendered_w = max(1, int(round(sw * scale)))
        rendered_h = max(1, int(round(sh * scale)))
        x = (avail_w - rendered_w) // 2
        y = (avail_h - rendered_h) // 2
        return QtCore.QRect(x, y, rendered_w, rendered_h)

    def recalculate_geometry(self) -> None:
        """Schedule lightweight geometry recalculation via debounce timer."""
        self._resize_timer.start(10)

    def _do_recalculate_geometry(self) -> None:
        """Execute contain/fill geometry fitting on child window."""
        self._position_overlay()
        if not self._embedded_container:
            return

        rect = self.calculate_fitted_geometry(
            self.width(),
            self.height(),
            self._target_w,
            self._target_h,
        )
        self._embedded_container.setGeometry(rect)

        gcd = math.gcd(rect.width(), rect.height())
        if gcd > 0:
            ratio_str = f"{rect.width() // gcd}:{rect.height() // gcd}"
        else:
            ratio_str = "1:1"

        self.geometry_updated.emit(rect.width(), rect.height(), ratio_str)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._do_recalculate_geometry()


class SyncHUD(QtWidgets.QFrame):
    """Status bar showing Android logical resolution, scrcpy stream, preview size, and sync status."""

    resync_requested = QtCore.Signal()
    reset_resolution_requested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #0E121A; border-top: 1px solid #1E2533; padding: 2px 6px; }"
            "QLabel { font-size: 11px; color: #94A3B8; }"
            "QPushButton { font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 3px; background-color: #1E2533; color: #E2E8F0; border: 1px solid #2D3748; }"
            "QPushButton:hover { background-color: #2D3748; color: #FFFFFF; }"
        )
        self.setFixedHeight(30)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        # Android Logical Dimension Label
        self.android_lbl = QtWidgets.QLabel("📱 Android: --")
        self.android_lbl.setToolTip("Logical resolution reported by Android ('wm size')")
        layout.addWidget(self.android_lbl)

        # Scrcpy Stream Dimension Label
        self.stream_lbl = QtWidgets.QLabel("📺 Stream: --")
        self.stream_lbl.setToolTip("Active scrcpy video stream texture resolution")
        layout.addWidget(self.stream_lbl)

        # Preview Dimension & Ratio Label
        self.preview_lbl = QtWidgets.QLabel("🖥 Preview: --")
        self.preview_lbl.setToolTip("Calculated fitted geometry inside SUSCRCPY container")
        layout.addWidget(self.preview_lbl)

        # Active Display Mode Badge
        self.mode_badge = QtWidgets.QLabel("[FIT]")
        self.mode_badge.setStyleSheet("color: #38BDF8; font-weight: 600; font-size: 10px;")
        layout.addWidget(self.mode_badge)

        # Live FPS Counter
        self.fps_lbl = QtWidgets.QLabel("")
        self.fps_lbl.setStyleSheet("color: #38BDF8; font-weight: 600;")
        layout.addWidget(self.fps_lbl)

        layout.addStretch()

        # Synchronization Status Badge
        self.sync_badge = QtWidgets.QLabel("● Idle")
        self.sync_badge.setStyleSheet("font-weight: 600; color: #94A3B8; margin-right: 4px;")
        layout.addWidget(self.sync_badge)

        # Quick Re-Sync Button
        self.resync_btn = QtWidgets.QPushButton("↻ Re-Sync")
        self.resync_btn.setToolTip("Re-query Android dimensions and refresh mirroring stream")
        self.resync_btn.clicked.connect(self.resync_requested)
        layout.addWidget(self.resync_btn)

        # Quick Reset Button
        self.reset_btn = QtWidgets.QPushButton("↺ Reset")
        self.reset_btn.setToolTip("Reset Android display override to hardware native physical size")
        self.reset_btn.clicked.connect(self.reset_resolution_requested)
        layout.addWidget(self.reset_btn)


class ScreenView(QtWidgets.QWidget):
    """Left-side container hosting the live embedded scrcpy screen, testing toolbar, and Sync HUD."""

    embedding_failed = QtCore.Signal(str)
    screenshot_requested = QtCore.Signal()
    recording_toggle_requested = QtCore.Signal()
    quick_note_requested = QtCore.Signal()
    quality_changed = QtCore.Signal(str)
    fullscreen_toggled = QtCore.Signal(bool)
    resync_requested = QtCore.Signal()
    reset_resolution_requested = QtCore.Signal()

    def __init__(
        self,
        scrcpy_manager: ScrcpyManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.scrcpy_mgr = scrcpy_manager
        self._embedder = get_window_embedder()
        self._window_id: Optional[int] = None

        self._android_w = 0
        self._android_h = 0
        self._stream_w = 0
        self._stream_h = 0
        self._preview_w = 0
        self._preview_h = 0
        self._preview_ratio = ""
        self._active_mode_str = "fit"

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

        # 1. Quick Testing Toolbar (Top)
        self.toolbar = QtWidgets.QFrame()
        self.toolbar.setStyleSheet("QFrame { background-color: #12161F; border-bottom: 1px solid #1E2533; padding: 4px; }")
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

        # Display Viewing Mode Dropdown (FIT, FILL, ORIGINAL)
        m_lbl = QtWidgets.QLabel("Mode:")
        m_lbl.setStyleSheet("color: #8DA2BC; font-size: 10px;")
        tb_layout.addWidget(m_lbl)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["FIT (Contain)", "FILL (Crop)", "ORIGINAL (1:1)"])
        self.mode_combo.setStyleSheet("font-size: 10px; padding: 2px 4px;")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        tb_layout.addWidget(self.mode_combo)

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

        # 2. Responsive Viewport Canvas (Center)
        self.canvas = ViewportCanvas(self)
        self.main_layout.addWidget(self.canvas, stretch=1)

        # 3. Synchronization HUD (Bottom)
        self.hud = SyncHUD(self)
        self.hud.resync_requested.connect(self.resync_requested)
        self.hud.reset_resolution_requested.connect(self.reset_resolution_requested)
        self.main_layout.addWidget(self.hud)

    def _connect_signals(self) -> None:
        self.scrcpy_mgr.started.connect(self._on_scrcpy_started)
        self.scrcpy_mgr.stopped.connect(self._on_scrcpy_stopped)
        self.scrcpy_mgr.stream_dimensions_changed.connect(self._on_stream_dimensions_changed)
        self.scrcpy_mgr.stream_fps_reported.connect(self._on_stream_fps_reported)
        self.canvas.geometry_updated.connect(self._on_preview_geometry_updated)

    def set_android_dimensions(self, width: int, height: int) -> None:
        """Update Android logical resolution value in HUD and canvas."""
        self._android_w = width
        self._android_h = height
        self.hud.android_lbl.setText(f"📱 Android: {width}×{height}")
        if self._stream_w == 0:
            self.canvas.set_target_dimensions(width, height)
        self._update_sync_status()

    def preview_profile_dimensions(self, width: int, height: int, profile_name: str) -> None:
        """Preview a profile's aspect ratio inside the canvas without changing device resolution."""
        logger.info("Previewing profile in ViewportCanvas: %s (%dx%d)", profile_name, width, height)
        self.canvas.set_target_dimensions(width, height)
        self.hud.sync_badge.setText(f"● Preview: {profile_name}")
        self.hud.sync_badge.setStyleSheet("font-weight: 600; color: #38BDF8;")
        self.canvas.show_updating_overlay(False)

    def set_updating_state(self, is_updating: bool, message: str = "⟳ Updating display...") -> None:
        """Show or hide the updating display overlay badge."""
        self.canvas.show_updating_overlay(is_updating, message)

    def _on_stream_dimensions_changed(self, width: int, height: int) -> None:
        """Update stream texture resolution value in HUD and canvas."""
        logger.info("Live stream dimensions received: %dx%d", width, height)
        self._stream_w = width
        self._stream_h = height
        self.canvas.show_updating_overlay(False)
        self.hud.stream_lbl.setText(f"📺 Stream: {width}×{height}")
        self.canvas.set_target_dimensions(width, height)
        self._update_sync_status()

    def _on_stream_fps_reported(self, fps: float) -> None:
        self.hud.fps_lbl.setText(f"⚡ {fps:.1f} fps")

    def _on_preview_geometry_updated(self, width: int, height: int, ratio_str: str) -> None:
        self._preview_w = width
        self._preview_h = height
        self._preview_ratio = ratio_str
        self.hud.preview_lbl.setText(f"🖥 Preview: {width}×{height} ({ratio_str})")

    def _update_sync_status(self) -> None:
        """Step 7: Compare Android logical and stream dimensions to show sync status."""
        if self._android_w <= 0 or self._stream_w <= 0:
            self.hud.sync_badge.setText("● Active")
            self.hud.sync_badge.setStyleSheet("font-weight: 600; color: #94A3B8;")
            return

        is_direct_match = (self._android_w == self._stream_w and self._android_h == self._stream_h)
        is_rotated_match = (self._android_w == self._stream_h and self._android_h == self._stream_w)

        if is_direct_match or is_rotated_match:
            self.hud.sync_badge.setText("● Synchronized")
            self.hud.sync_badge.setStyleSheet("font-weight: 600; color: #10B981;")
            self.hud.sync_badge.setToolTip("Android logical display and scrcpy stream dimensions are perfectly synchronized.")
        else:
            self.hud.sync_badge.setText("⚠️ Mismatch")
            self.hud.sync_badge.setStyleSheet("font-weight: 600; color: #F59E0B;")
            self.hud.sync_badge.setToolTip(
                f"Dimension mismatch:\nAndroid: {self._android_w}x{self._android_h}\n"
                f"Stream:  {self._stream_w}x{self._stream_h}\nClick Re-Sync to align."
            )

    def _on_mode_changed(self, text: str) -> None:
        if "FILL" in text:
            self._active_mode_str = "fill"
            self.canvas.set_display_mode("fill")
            self.hud.mode_badge.setText("[FILL — ✂ Crop Active]")
            self.hud.mode_badge.setStyleSheet("color: #F59E0B; font-weight: 600; font-size: 10px;")
        elif "ORIGINAL" in text:
            self._active_mode_str = "original"
            self.canvas.set_display_mode("original")
            self.hud.mode_badge.setText("[ORIGINAL (1:1)]")
            self.hud.mode_badge.setStyleSheet("color: #A78BFA; font-weight: 600; font-size: 10px;")
        else:
            self._active_mode_str = "fit"
            self.canvas.set_display_mode("fit")
            self.hud.mode_badge.setText("[FIT]")
            self.hud.mode_badge.setStyleSheet("color: #38BDF8; font-weight: 600; font-size: 10px;")

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
            self.rec_btn.setStyleSheet(
                "padding: 3px 8px; font-size: 11px; font-weight: 600; background-color: #EF4444; color: white; border-radius: 3px;"
            )
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

        self.canvas.status_title.setText("Embedding Live Android Screen...")
        self.canvas.status_desc.setText(f"Synchronizing session: {window_title}")
        self.canvas.wayland_banner.setVisible(False)

        if not self._embedder:
            self._embedder = get_window_embedder()

        if self._embedder:
            self._poll_timer.start()
        else:
            diag = WaylandHelper.get_diagnostics()
            self.canvas.wayland_banner.setVisible(True)
            self.canvas.wb_text.setText(diag.guidance_message)
            self.canvas.status_title.setText("scrcpy Running (Companion Mode)")
            self.canvas.status_desc.setText("Display server restricted cross-process window reparenting.")

    def _check_and_embed(self) -> None:
        """Poll for foreign scrcpy window and embed once ready."""
        self._poll_attempts += 1
        if not self._pending_title or not self._embedder:
            self._poll_timer.stop()
            return

        wid = self._embedder.find_window(self._pending_title, self._pending_pid, timeout=0.1)
        if wid:
            self._poll_timer.stop()
            logger.info("Found native window 0x%x; embedding into canvas...", wid)
            self._window_id = wid
            self._embed_native_window(wid)
            return

        if self._poll_attempts > 60:  # ~5 seconds
            self._poll_timer.stop()
            logger.warning("Scrcpy window embedding timed out; keeping external window.")
            self.canvas.status_title.setText("scrcpy Screen Active (External Window)")
            self.canvas.status_desc.setText("The mirroring session is active in its native window.")

    def _embed_native_window(self, window_id: int) -> None:
        """Reparent foreign window into canvas."""
        if not self._embedder:
            return

        container = self._embedder.embed_window(window_id, self.canvas)
        if container:
            self.canvas.attach_container(container)
            logger.info("Native window 0x%x embedded successfully into ViewportCanvas.", window_id)
        else:
            self.canvas.placeholder.setVisible(True)
            self.canvas.status_title.setText("Window Embedding Unsupported")
            self.canvas.status_desc.setText("Foreign window could not be reparented in this session.")

    def _on_scrcpy_stopped(self, exit_code: int) -> None:
        """Clean up embedded container when scrcpy terminates."""
        self._poll_timer.stop()
        self.canvas.detach_container()
        self._window_id = None
        self._pending_title = None
        self._pending_pid = None
        self._stream_w = 0
        self._stream_h = 0
        self.canvas.show_updating_overlay(False)
        self.hud.stream_lbl.setText("📺 Stream: --")
        self.hud.fps_lbl.setText("")
        self._update_sync_status()

        self.canvas.placeholder.setVisible(True)
        self.canvas.status_title.setText("No Active Display Mirror")
        self.canvas.status_desc.setText("Select a device or resolution ratio to restart screen mirroring.")
        self.canvas.wayland_banner.setVisible(False)

    def reset_view(self) -> None:
        """Reset view to clean disconnected state."""
        self._on_scrcpy_stopped(0)
        self._android_w = 0
        self._android_h = 0
        self.hud.android_lbl.setText("📱 Android: --")
        self.hud.preview_lbl.setText("🖥 Preview: --")
        self.canvas.status_title.setText("No Active Display Mirror")
        self.canvas.status_desc.setText("Connect an Android device with USB Debugging enabled.")
