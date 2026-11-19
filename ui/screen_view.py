"""Embedded live Android screen for SUSCRCPY.

Hosts the scrcpy window inside the left pane, keeps it left-anchored and fully
visible for every aspect ratio, and reports exact device / stream / view metrics.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.screen_manager import ScreenManager
from core.scrcpy_manager import ScrcpyManager
from display_backend import get_window_embedder
from display_backend.linux_wayland import WaylandHelper

logger = logging.getLogger("suscrcpy.ui.screen_view")

CANVAS_PADDING = 8
# Poll for the native window while scrcpy starts up. The window is never reparented
# until the display server reports it as mapped/visible.
EMBED_POLL_INTERVAL_MS = 120
EMBED_READY_TIMEOUT_S = 60.0


def ratio_text(width: int, height: int) -> str:
    """Exact ratio label for a pair of pixel dimensions."""
    if width <= 0 or height <= 0:
        return "--"
    return ScreenManager.ratio_label(width, height)


class ViewportCanvas(QtWidgets.QWidget):
    """Black canvas that keeps the mirrored screen left-anchored and fully visible."""

    geometry_updated = QtCore.Signal(int, int, float)  # view_w, view_h, scale

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("viewportCanvas")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self.setMinimumSize(320, 320)

        self._embedded_container: Optional[QtWidgets.QWidget] = None
        self._target_w = 0
        self._target_h = 0
        self._mode = "fit"

        self._resize_timer = QtCore.QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(10)
        self._resize_timer.timeout.connect(self._recalculate)

        self._build_placeholder()

    # ------------------------------------------------------------------ ui
    def _build_placeholder(self) -> None:
        self._placeholder = QtWidgets.QFrame(self)
        self._placeholder.setObjectName("viewportPlaceholder")
        layout = QtWidgets.QVBoxLayout(self._placeholder)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(6)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.status_title = QtWidgets.QLabel("No device mirror")
        self.status_title.setObjectName("placeholderTitle")
        self.status_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.status_desc = QtWidgets.QLabel(
            "Connect an Android device with USB debugging enabled."
        )
        self.status_desc.setObjectName("placeholderText")
        self.status_desc.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.status_desc.setWordWrap(True)

        layout.addWidget(self.status_title)
        layout.addWidget(self.status_desc)

        self.wayland_banner = QtWidgets.QLabel("")
        self.wayland_banner.setObjectName("waylandBanner")
        self.wayland_banner.setWordWrap(True)
        self.wayland_banner.setVisible(False)
        layout.addWidget(self.wayland_banner)

        self.updating_badge = QtWidgets.QLabel("Applying display change...")
        self.updating_badge.setObjectName("updatingBadge")
        self.updating_badge.setVisible(False)
        layout.addWidget(self.updating_badge)

    # -------------------------------------------------------------- attach
    def attach_container(self, container: QtWidgets.QWidget) -> None:
        self._placeholder.setVisible(False)
        self._embedded_container = container
        container.setParent(self)
        container.show()
        container.setFocus()
        self._recalculate()

    def detach_container(self) -> None:
        if self._embedded_container is not None:
            self._embedded_container.setParent(None)
            self._embedded_container.deleteLater()
            self._embedded_container = None
        self._placeholder.setVisible(True)
        self._recalculate()
        self.geometry_updated.emit(0, 0, 0.0)

    def has_stream(self) -> bool:
        return self._embedded_container is not None

    # ------------------------------------------------------------- geometry
    def set_target_dimensions(self, width: int, height: int) -> None:
        if width > 0 and height > 0:
            self._target_w = width
            self._target_h = height
            self._schedule()

    def set_display_mode(self, mode: str) -> None:
        self._mode = mode
        self._schedule()

    def show_updating_overlay(self, show: bool, text: str = "") -> None:
        if text:
            self.updating_badge.setText(text)
        self.updating_badge.setVisible(show)

    def _schedule(self) -> None:
        self._resize_timer.start(10)

    def _recalculate(self) -> None:
        if self._embedded_container is not None and self._target_w > 0:
            rect, scale = self.fitted_rect()
            self._embedded_container.setGeometry(rect)
            self.geometry_updated.emit(rect.width(), rect.height(), scale)
        self._position_placeholder()

    def fitted_rect(self) -> tuple[QtCore.QRect, float]:
        """Compute the on-screen rect: left-anchored, vertically centred, never clipped."""
        available_w = max(1, self.width() - 2 * CANVAS_PADDING)
        available_h = max(1, self.height() - 2 * CANVAS_PADDING)
        ratio = self._target_w / self._target_h if self._target_h else 1.0

        if self._mode == "original":
            scale = min(1.0, available_w / self._target_w, available_h / self._target_h)
            view_w = max(1, int(round(self._target_w * scale)))
            view_h = max(1, int(round(self._target_h * scale)))
        elif self._mode == "fill":
            scale = max(available_w / self._target_w, available_h / self._target_h)
            view_w = int(round(self._target_w * scale))
            view_h = int(round(self._target_h * scale))
        else:  # fit: whole screen visible
            scale = min(available_w / self._target_w, available_h / self._target_h)
            view_w = max(1, int(round(self._target_w * scale)))
            view_h = max(1, int(round(self._target_h * scale)))

        # Keep the requested aspect ratio exact after rounding, shrinking a pixel at a
        # time if rounding pushed the mirror past the canvas edge.
        view_h = max(1, int(round(view_w / ratio)))
        if self._mode != "fill":
            while (view_w > available_w or view_h > available_h) and view_w > 1:
                view_w -= 1
                view_h = max(1, int(round(view_w / ratio)))

        x = CANVAS_PADDING                     # left-anchored on every ratio
        y = CANVAS_PADDING + (available_h - view_h) // 2
        if view_h <= available_h:
            y = max(CANVAS_PADDING, y)
        return QtCore.QRect(x, y, view_w, view_h), scale

    def _position_placeholder(self) -> None:
        if self.has_stream():
            self._placeholder.setVisible(False)
            return
        self._placeholder.setVisible(True)
        width = min(max(300, self.width() - 80), 460)
        self._placeholder.setFixedWidth(width)
        self._placeholder.adjustSize()
        self._placeholder.move(
            CANVAS_PADDING + 24,
            max(CANVAS_PADDING, (self.height() - self._placeholder.height()) // 2),
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._recalculate()


class SyncBar(QtWidgets.QFrame):
    """Compact status strip: device size, stream size, view size and sync state."""

    resync_requested = QtCore.Signal()
    reset_resolution_requested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("syncBar")
        self.setFixedHeight(30)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(9)

        self.device_lbl = QtWidgets.QLabel("Device --")
        self.device_lbl.setToolTip("Logical resolution Android is currently rendering")
        layout.addWidget(self.device_lbl)

        self.stream_lbl = QtWidgets.QLabel("Stream --")
        self.stream_lbl.setToolTip("Resolution of the decoded scrcpy video stream")
        layout.addWidget(self.stream_lbl)

        self.view_lbl = QtWidgets.QLabel("View --")
        self.view_lbl.setToolTip("Size of the mirror inside this window")
        layout.addWidget(self.view_lbl)

        self.mode_lbl = QtWidgets.QLabel("FIT")
        self.mode_lbl.setObjectName("modeBadge")
        layout.addWidget(self.mode_lbl)

        layout.addStretch(1)

        self.sync_lbl = QtWidgets.QLabel("Idle")
        self.sync_lbl.setObjectName("syncIdle")
        layout.addWidget(self.sync_lbl)

        self.resync_btn = QtWidgets.QPushButton("Re-sync")
        self.resync_btn.setObjectName("ghostBtn")
        self.resync_btn.setToolTip("Re-read the device resolution and restart the stream")
        self.resync_btn.clicked.connect(self.resync_requested)
        layout.addWidget(self.resync_btn)


class ScreenView(QtWidgets.QWidget):
    """Left pane: mirror toolbar, live screen canvas and sync bar."""

    screenshot_requested = QtCore.Signal()
    mode_changed = QtCore.Signal(str)
    quality_changed = QtCore.Signal(str)
    fullscreen_toggled = QtCore.Signal(bool)
    resync_requested = QtCore.Signal()
    reset_resolution_requested = QtCore.Signal()

    def __init__(self, scrcpy_manager: ScrcpyManager, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.scrcpy_mgr = scrcpy_manager
        self._embedder = get_window_embedder()
        self._window_id: Optional[int] = None
        self._pending_title: Optional[str] = None
        self._pending_pid: Optional[int] = None
        self._poll_attempts = 0
        self._embed_deadline = 0.0
        self._embed_abandoned = False
        self._android_w = 0
        self._android_h = 0
        self._stream_w = 0
        self._stream_h = 0
        self._is_fullscreen = False

        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(EMBED_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._check_and_embed)

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QFrame()
        toolbar.setObjectName("mirrorToolbar")
        bar = QtWidgets.QHBoxLayout(toolbar)
        bar.setContentsMargins(8, 6, 8, 6)
        bar.setSpacing(8)

        self.shot_btn = QtWidgets.QPushButton("Screenshot")
        self.shot_btn.setToolTip("Capture the device screen  (Ctrl+Shift+S)")
        self.shot_btn.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self.shot_btn.clicked.connect(self.screenshot_requested)
        bar.addWidget(self.shot_btn)

        bar.addSpacing(6)

        mode_label = QtWidgets.QLabel("Scaling")
        mode_label.setObjectName("inlineLabel")
        bar.addWidget(mode_label)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Fit", "Fill", "Original"])
        self.mode_combo.setToolTip("Fit keeps the whole screen visible, Fill crops, Original is 1:1")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        bar.addWidget(self.mode_combo)

        quality_label = QtWidgets.QLabel("Quality")
        quality_label.setObjectName("inlineLabel")
        bar.addWidget(quality_label)

        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItems(["Balanced", "Performance", "Native"])
        self.quality_combo.currentTextChanged.connect(self._on_quality_changed)
        bar.addWidget(self.quality_combo)

        bar.addStretch(1)

        self.fullscreen_btn = QtWidgets.QPushButton("Fullscreen")
        self.fullscreen_btn.setObjectName("ghostBtn")
        self.fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        bar.addWidget(self.fullscreen_btn)

        root.addWidget(toolbar)

        self.canvas = ViewportCanvas(self)
        root.addWidget(self.canvas, stretch=1)

        self.sync_bar = SyncBar(self)
        self.sync_bar.resync_requested.connect(self.resync_requested)
        self.sync_bar.reset_resolution_requested.connect(self.reset_resolution_requested)
        root.addWidget(self.sync_bar)

    def _connect_signals(self) -> None:
        self.scrcpy_mgr.started.connect(self._on_scrcpy_started)
        self.scrcpy_mgr.stopped.connect(self._on_scrcpy_stopped)
        self.scrcpy_mgr.stream_dimensions_changed.connect(self._on_stream_dimensions)
        self.canvas.geometry_updated.connect(self._on_view_geometry)

    # -------------------------------------------------------------- state
    def set_android_dimensions(self, width: int, height: int) -> None:
        self._android_w = width
        self._android_h = height
        self.sync_bar.device_lbl.setText(f"Device {width}\u00d7{height}")
        self.sync_bar.device_lbl.setToolTip(
            f"Logical resolution Android is rendering ({ratio_text(width, height)})"
        )
        if self._stream_w == 0:
            self.canvas.set_target_dimensions(width, height)
        self._update_sync_state()

    def set_updating_state(self, active: bool, message: str = "") -> None:
        self.canvas.show_updating_overlay(active, message)
        if not active:
            self._update_sync_state()

    def set_quality(self, profile: str) -> None:
        labels = {"performance": "Performance", "high": "Native", "balanced": "Balanced"}
        self.quality_combo.blockSignals(True)
        self.quality_combo.setCurrentText(labels.get(profile, "Balanced"))
        self.quality_combo.blockSignals(False)

    def reset_view(self) -> None:
        self._on_scrcpy_stopped(0)
        self._android_w = self._android_h = 0
        self.sync_bar.device_lbl.setText("Device --")
        self.sync_bar.view_lbl.setText("View --")
        self.canvas.status_title.setText("No device mirror")
        self.canvas.status_desc.setText("Connect an Android device with USB debugging enabled.")

    # ------------------------------------------------------------- stream
    def _on_stream_dimensions(self, width: int, height: int) -> None:
        self._stream_w = width
        self._stream_h = height
        self.canvas.show_updating_overlay(False)
        self.sync_bar.stream_lbl.setText(f"Stream {width}\u00d7{height}")
        self.canvas.set_target_dimensions(width, height)
        self._update_sync_state()
        # scrcpy reveals its window on the first decoded frame. Reparenting it any
        # earlier (while it is still hidden and the renderer is being set up) makes
        # scrcpy die with SIGFPE, so embedding waits for this moment.
        self._start_embed_poll()

    def _on_view_geometry(self, width: int, height: int, scale: float) -> None:
        if width <= 0:
            self.sync_bar.view_lbl.setText("View --")
            return
        self.sync_bar.view_lbl.setText(f"View {width}\u00d7{height}  ({scale * 100:.0f}%)")

    def _update_sync_state(self) -> None:
        """Sync means the stream keeps the device aspect ratio (scaled by max-size)."""
        if not self._stream_w or not self._stream_h:
            self.sync_bar.sync_lbl.setText("\u25cf Idle")
            self.sync_bar.sync_lbl.setObjectName("syncIdle")
            self.sync_bar.sync_lbl.setToolTip("No video stream is running")
            self._restyle_sync()
            return

        if not self._android_w or not self._android_h:
            self.sync_bar.sync_lbl.setText("\u25cf Streaming")
            self.sync_bar.sync_lbl.setObjectName("syncIdle")
            self._restyle_sync()
            return

        device_ratio = self._android_w / self._android_h
        stream_ratio = self._stream_w / self._stream_h
        device_shape = self._android_w >= self._android_h
        stream_shape = self._stream_w >= self._stream_h
        drift = abs(device_ratio - stream_ratio) / device_ratio

        if device_shape == stream_shape and drift <= 0.01:
            self.sync_bar.sync_lbl.setText("\u2713 Synced")
            self.sync_bar.sync_lbl.setObjectName("syncOk")
            self.sync_bar.sync_lbl.setToolTip("Stream and device resolutions have the same aspect ratio.")
        else:
            self.sync_bar.sync_lbl.setText("\u26a0 Desync")
            self.sync_bar.sync_lbl.setObjectName("syncBad")
            self.sync_bar.sync_lbl.setToolTip(
                f"Device {self._android_w}x{self._android_h} vs stream "
                f"{self._stream_w}x{self._stream_h}. Press Re-sync."
            )
        self._restyle_sync()

    def _restyle_sync(self) -> None:
        self.sync_bar.sync_lbl.style().unpolish(self.sync_bar.sync_lbl)
        self.sync_bar.sync_lbl.style().polish(self.sync_bar.sync_lbl)

    # ------------------------------------------------------------- scrcpy
    def _on_scrcpy_started(self, window_title: str) -> None:
        self._pending_title = window_title
        process = self.scrcpy_mgr.current_proc
        self._pending_pid = process.pid if process else None
        self._poll_attempts = 0
        self._embed_abandoned = False
        self._embed_deadline = time.monotonic() + EMBED_READY_TIMEOUT_S

        self.canvas.status_title.setText("Starting mirror...")
        self.canvas.status_desc.setText("Waiting for the scrcpy window.")
        self.canvas.wayland_banner.setVisible(False)

        if self._embedder is None:
            self._embedder = get_window_embedder()

        # Fallback only starts *looking* for the window if the first-frame report never
        # arrives. It cannot weaken the safety gate: _check_and_embed still refuses to
        # reparent a window the display server has not mapped yet.
        QtCore.QTimer.singleShot(3000, self._start_embed_poll)

        if self._embedder is None:
            diagnostics = WaylandHelper.get_diagnostics()
            self.canvas.wayland_banner.setText(diagnostics.guidance_message)
            self.canvas.wayland_banner.setVisible(True)
            self.canvas.status_title.setText("scrcpy running in its own window")
            self.canvas.status_desc.setText(
                "This session cannot reparent native windows. Start SUSCRCPY with "
                "QT_QPA_PLATFORM=xcb to embed the screen here."
            )

    def _start_embed_poll(self) -> None:
        """Begin looking for the scrcpy window once it is actually shown."""
        if self._embedder is None or not self._pending_title or self._embed_abandoned:
            return
        if self._window_id or self._poll_timer.isActive():
            return
        if self._embed_deadline <= 0:
            self._embed_deadline = time.monotonic() + EMBED_READY_TIMEOUT_S
        self._poll_attempts = 0
        self._poll_timer.start()

    def _check_and_embed(self) -> None:
        """Embed only a window the display server reports as mapped.

        There is deliberately no attempt-count bypass here: reparenting scrcpy's still
        hidden pre-first-frame window is what produces the SIGFPE (exit code -8), so the
        window is either proven visible or it stays in its own window.
        """
        self._poll_attempts += 1
        if not self._pending_title or not self._embedder:
            self._poll_timer.stop()
            return

        window_id = self._embedder.find_window(self._pending_title, self._pending_pid, timeout=0.1)
        if not window_id:
            if time.monotonic() >= self._embed_deadline:
                self._abandon_embedding("The scrcpy window never appeared.")
            return

        if not self._embedder.is_window_ready(window_id):
            if time.monotonic() >= self._embed_deadline:
                self._abandon_embedding("scrcpy never confirmed a visible first frame.")
            return

        self._poll_timer.stop()
        self._window_id = window_id
        self._embed_native_window(window_id)

    def _abandon_embedding(self, reason: str) -> None:
        """Give up safely: the mirror keeps running in its own top-level window."""
        self._poll_timer.stop()
        self._embed_abandoned = True
        self._window_id = None
        logger.warning("Embedding skipped: %s", reason)
        self.canvas.status_title.setText("Mirror running in its own window")
        self.canvas.status_desc.setText(
            f"{reason} The device screen is still live \u2014 use Fullscreen if it is "
            "hidden behind this window."
        )

    def _embed_native_window(self, window_id: int) -> None:
        if not self._embedder:
            return
        container = self._embedder.embed_window(window_id, self.canvas)
        if container is not None:
            self.canvas.attach_container(container)
            logger.info("Embedded scrcpy window 0x%x", window_id)
        else:
            self.canvas.status_title.setText("Cannot embed window")
            self.canvas.status_desc.setText(
                "The display server refused to reparent the scrcpy window."
            )

    def _on_scrcpy_stopped(self, exit_code: int) -> None:
        self._poll_timer.stop()
        self.canvas.detach_container()
        self._window_id = None
        self._pending_title = None
        self._pending_pid = None
        self._embed_deadline = 0.0
        self._embed_abandoned = False
        self._stream_w = self._stream_h = 0
        self.canvas.show_updating_overlay(False)
        self.sync_bar.stream_lbl.setText("Stream --")
        self._update_sync_state()
        if exit_code not in (0, None):
            self.canvas.status_title.setText("Mirror stopped")
            self.canvas.status_desc.setText(
                f"scrcpy exited with code {exit_code}. Press Re-sync to restart the mirror."
            )
        else:
            self.canvas.status_title.setText("No device mirror")
            self.canvas.status_desc.setText("Select a device or apply a ratio to start the mirror.")
        self.canvas.wayland_banner.setVisible(False)

    # ------------------------------------------------------------- actions
    def _on_mode_changed(self, text: str) -> None:
        mode = {"Fill": "fill", "Original": "original"}.get(text, "fit")
        self.canvas.set_display_mode(mode)
        self.sync_bar.mode_lbl.setText(mode.upper())
        self.mode_changed.emit(mode)

    def _on_quality_changed(self, text: str) -> None:
        quality = {"Performance": "performance", "Native": "high"}.get(text, "balanced")
        self.quality_changed.emit(quality)

    def _toggle_fullscreen(self) -> None:
        self._is_fullscreen = not self._is_fullscreen
        self.fullscreen_toggled.emit(self._is_fullscreen)
