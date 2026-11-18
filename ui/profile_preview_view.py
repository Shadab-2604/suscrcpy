"""Visual Screen Profile and Responsive Layout Preview (Mode 2) for SUSCRCPY 2.1.

Simulates device viewports, orientation rotations, safe areas, camera cutouts,
foldable postures, circular smartwatch clipping masks, dual-monitors, and XR stereo displays.
"""
from __future__ import annotations

import logging
import math
from typing import Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from core.profile_model import ScreenProfile

logger = logging.getLogger("suscrcpy.ui.profile_preview_view")


class ViewportCanvas(QtWidgets.QWidget):
    """Custom paint canvas rendering realistic simulated screen geometry."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.profile: Optional[ScreenProfile] = None
        self.rotation_deg = 0  # 0, 90, 180, 270
        self.show_safe_areas = True
        self.show_cutouts = True
        self.show_mask = True
        self.show_grid = True
        self.zoom_factor = 1.0  # 1.0 = fit
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

    def set_profile(self, profile: ScreenProfile) -> None:
        self.profile = profile
        self.rotation_deg = 0
        self.update()

    def set_rotation(self, deg: int) -> None:
        self.rotation_deg = deg % 360
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QtGui.QColor("#080b0f"))

        if not self.profile:
            painter.setPen(QtGui.QColor("#8b949e"))
            painter.setFont(QtGui.QFont("Segoe UI", 13))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "Select a profile from the library to preview.")
            return

        p = self.profile
        # Determine current effective orientation
        is_rotated_90_270 = self.rotation_deg in (90, 270)
        base_w = p.resolution.width_px
        base_h = p.resolution.height_px

        target_w = base_h if is_rotated_90_270 else base_w
        target_h = base_w if is_rotated_90_270 else base_h

        # Available canvas rect with margin
        margin = 40
        avail_w = max(100, self.width() - (margin * 2))
        avail_h = max(100, self.height() - (margin * 2))

        # Calculate scale to fit canvas
        fit_scale = min(avail_w / target_w, avail_h / target_h)
        scale = fit_scale * self.zoom_factor

        draw_w = target_w * scale
        draw_h = target_h * scale
        start_x = (self.width() - draw_w) / 2
        start_y = (self.height() - draw_h) / 2
        screen_rect = QtCore.QRectF(start_x, start_y, draw_w, draw_h)

        # 1. Outer Bezel / Device Frame
        bezel_margin = 12 * min(1.5, max(0.6, scale * 3))
        outer_rect = screen_rect.adjusted(-bezel_margin, -bezel_margin, bezel_margin, bezel_margin)

        corner_radius = 24 * scale if p.category in ("smartphone", "tablet", "foldable") else 6 * scale
        if p.shape == "round":
            painter.setBrush(QtGui.QColor("#161b22"))
            painter.setPen(QtGui.QPen(QtGui.QColor("#30363d"), 3))
            painter.drawEllipse(outer_rect)
        else:
            painter.setBrush(QtGui.QColor("#161b22"))
            painter.setPen(QtGui.QPen(QtGui.QColor("#30363d"), 3))
            painter.drawRoundedRect(outer_rect, corner_radius + 4, corner_radius + 4)

        # 2. Display Surface
        painter.save()
        if p.shape == "round":
            clip_path = QtGui.QPainterPath()
            clip_path.addEllipse(screen_rect)
            painter.setClipPath(clip_path)
            painter.fillRect(screen_rect, QtGui.QColor("#0d1117"))
        else:
            clip_path = QtGui.QPainterPath()
            clip_path.addRoundedRect(screen_rect, corner_radius, corner_radius)
            painter.setClipPath(clip_path)
            painter.fillRect(screen_rect, QtGui.QColor("#0d1117"))

        # 3. XR Dual-Eye Viewport rendering
        if p.xr.enabled and p.xr.stereo_mode == "side_by_side":
            half_w = draw_w / 2
            left_rect = QtCore.QRectF(start_x, start_y, half_w, draw_h)
            right_rect = QtCore.QRectF(start_x + half_w, start_y, half_w, draw_h)

            painter.setPen(QtGui.QPen(QtGui.QColor("#388bfd"), 1, QtCore.Qt.PenStyle.DashLine))
            painter.drawLine(QtCore.QPointF(start_x + half_w, start_y), QtCore.QPointF(start_x + half_w, start_y + draw_h))

            # Left Eye Label
            painter.setPen(QtGui.QColor("#58a6ff"))
            painter.setFont(QtGui.QFont("Segoe UI", int(max(9, 11 * scale))))
            painter.drawText(left_rect.adjusted(10, 10, -10, -10), QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignHCenter, f"LEFT EYE ({p.xr.per_eye_width_px}×{p.xr.per_eye_height_px})")
            painter.drawText(right_rect.adjusted(10, 10, -10, -10), QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignHCenter, f"RIGHT EYE ({p.xr.per_eye_width_px}×{p.xr.per_eye_height_px})")

            # Stereo Reticle Circles
            painter.setPen(QtGui.QPen(QtGui.QColor("#238636"), 1))
            painter.drawEllipse(left_rect.center(), min(half_w, draw_h) * 0.35, min(half_w, draw_h) * 0.35)
            painter.drawEllipse(right_rect.center(), min(half_w, draw_h) * 0.35, min(half_w, draw_h) * 0.35)

        # 4. Dual-Monitor Visualization
        elif p.dual_screen.enabled:
            half_w = draw_w / 2
            painter.setPen(QtGui.QPen(QtGui.QColor("#d29922"), 2, QtCore.Qt.PenStyle.SolidLine))
            painter.drawLine(QtCore.QPointF(start_x + half_w, start_y), QtCore.QPointF(start_x + half_w, start_y + draw_h))
            painter.setPen(QtGui.QColor("#e3b341"))
            painter.drawText(screen_rect.adjusted(10, 10, -10, -10), QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft, "MONITOR 1 (Primary)")
            painter.drawText(screen_rect.adjusted(half_w + 10, 10, -10, -10), QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft, "MONITOR 2 (Secondary)")

        # 5. Responsive Content Test Grid
        if self.show_grid:
            self._draw_responsive_grid(painter, screen_rect, scale)

        # 6. Safe Area Guides
        if self.show_safe_areas:
            sa = p.safe_areas
            sa_rect = QtCore.QRectF(
                start_x + (sa.left * scale),
                start_y + (sa.top * scale),
                draw_w - ((sa.left + sa.right) * scale),
                draw_h - ((sa.top + sa.bottom) * scale),
            )
            painter.setPen(QtGui.QPen(QtGui.QColor("#3fb950"), 1.5, QtCore.Qt.PenStyle.DashLine))
            painter.drawRect(sa_rect)

            painter.setFont(QtGui.QFont("Segoe UI", 9))
            painter.setPen(QtGui.QColor("#7ee787"))
            painter.drawText(sa_rect.adjusted(6, 6, 0, 0), "Content Safe Boundary")

        # 7. Foldable Hinge Guide
        if p.foldable.enabled and p.foldable.hinge:
            hinge = p.foldable.hinge
            h_pos = hinge.get("position", base_w // 2) * scale
            h_width = max(4.0, hinge.get("width", 10) * scale)

            painter.setBrush(QtGui.QColor(80, 80, 80, 140))
            painter.setPen(QtGui.QPen(QtGui.QColor("#58a6ff"), 1, QtCore.Qt.PenStyle.DashDotLine))
            if hinge.get("orientation") == "horizontal":
                h_rect = QtCore.QRectF(start_x, start_y + h_pos - (h_width / 2), draw_w, h_width)
            else:
                h_rect = QtCore.QRectF(start_x + h_pos - (h_width / 2), start_y, h_width, draw_h)
            painter.drawRect(h_rect)

        # 8. Hardware Cutouts (Punch hole, Notch, Dynamic Island)
        if self.show_cutouts:
            painter.setBrush(QtGui.QColor("#000000"))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            for c in p.cutouts:
                cx = start_x + (c.x * scale) - ((c.width * scale) / 2)
                cy = start_y + (c.y * scale) - ((c.height * scale) / 2)
                cw = c.width * scale
                ch = c.height * scale

                if c.type in ("dynamic_island", "pill"):
                    painter.drawRoundedRect(QtCore.QRectF(cx, cy, cw, ch), ch / 2, ch / 2)
                elif c.type == "punch_hole":
                    painter.drawEllipse(QtCore.QRectF(cx, cy, cw, ch))
                else:  # notch
                    painter.drawRoundedRect(QtCore.QRectF(cx, start_y, cw, ch), 8 * scale, 8 * scale)

        # 9. Wearable Round Clipping Mask Warning
        if p.shape == "round" and self.show_mask:
            painter.setPen(QtGui.QPen(QtGui.QColor("#f85149"), 1, QtCore.Qt.PenStyle.DotLine))
            # Inner safe content square inside circle
            side = draw_w / math.sqrt(2)
            sq_x = start_x + ((draw_w - side) / 2)
            sq_y = start_y + ((draw_h - side) / 2)
            painter.drawRect(QtCore.QRectF(sq_x, sq_y, side, side))

            painter.setFont(QtGui.QFont("Segoe UI", 9))
            painter.setPen(QtGui.QColor("#ff7b72"))
            painter.drawText(QtCore.QRectF(sq_x, sq_y, side, 20), QtCore.Qt.AlignmentFlag.AlignCenter, "Watch Text Safe Area")

        painter.restore()

        # Canvas Border
        painter.setPen(QtGui.QPen(QtGui.QColor("#30363d"), 1))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _draw_responsive_grid(self, painter: QtGui.QPainter, rect: QtCore.QRectF, scale: float) -> None:
        """Draw realistic UI layout elements demonstrating responsive behavior."""
        painter.setFont(QtGui.QFont("Segoe UI", int(max(8, 10 * scale))))
        painter.setPen(QtGui.QColor("#8b949e"))

        # App Bar / Header simulation
        header_h = 48 * scale
        header_rect = QtCore.QRectF(rect.x(), rect.y() + (24 * scale), rect.width(), header_h)
        painter.setBrush(QtGui.QColor("#161b22"))
        painter.drawRect(header_rect)
        painter.setPen(QtGui.QColor("#f0f6fc"))
        painter.drawText(header_rect.adjusted(12 * scale, 0, 0, 0), QtCore.Qt.AlignmentFlag.AlignVCenter, f"{self.profile.model} Viewport Preview")

        # Responsive Cards
        card_margin = 12 * scale
        top_y = header_rect.bottom() + card_margin
        avail_h = rect.bottom() - top_y - (56 * scale)

        cols = 3 if rect.width() > 700 else (2 if rect.width() > 400 else 1)
        card_w = (rect.width() - (card_margin * (cols + 1))) / cols
        card_h = min(120 * scale, avail_h / 2)

        for i in range(min(cols * 2, 6)):
            row = i // cols
            col = i % cols
            cx = rect.x() + card_margin + (col * (card_w + card_margin))
            cy = top_y + (row * (card_h + card_margin))

            if cy + card_h > rect.bottom() - (40 * scale):
                break

            card_rect = QtCore.QRectF(cx, cy, card_w, card_h)
            painter.setBrush(QtGui.QColor("#21262d"))
            painter.setPen(QtGui.QColor("#30363d"))
            painter.drawRoundedRect(card_rect, 6 * scale, 6 * scale)

            painter.setPen(QtGui.QColor("#c9d1d9"))
            painter.drawText(card_rect.adjusted(8, 8, -8, -8), QtCore.Qt.AlignmentFlag.AlignTop, f"Card Component #{i + 1}\n{int(card_w / scale)}×{int(card_h / scale)} dp")


class ProfilePreviewView(QtWidgets.QWidget):
    """Container hosting the Mode 2 Screen Profile Preview workspace and tools."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Mode Banner
        banner = QtWidgets.QFrame()
        banner.setStyleSheet("background-color: #1f2d3d; border: 1px solid #388bfd; border-radius: 5px; padding: 6px;")
        b_layout = QtWidgets.QHBoxLayout(banner)
        b_layout.setContentsMargins(8, 4, 8, 4)

        b_title = QtWidgets.QLabel("📐 Mode 2: Screen Profile & Viewport Preview")
        b_title.setStyleSheet("font-weight: 700; color: #58a6ff; font-size: 13px;")
        b_layout.addWidget(b_title)

        b_desc = QtWidgets.QLabel("• Layout Simulation Canvas (Not an OS Emulator) • Test responsive breakpoints & hardware cutouts")
        b_desc.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        b_layout.addWidget(b_desc)
        b_layout.addStretch()

        self.size_badge = QtWidgets.QLabel("Class: Compact")
        self.size_badge.setStyleSheet("background-color: #238636; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;")
        b_layout.addWidget(self.size_badge)

        layout.addWidget(banner)

        # Controls Tool Bar
        tb_layout = QtWidgets.QHBoxLayout()
        tb_layout.setSpacing(8)

        tb_layout.addWidget(QtWidgets.QLabel("Orientation:"))
        self.rot_0_btn = QtWidgets.QPushButton("0° Portrait")
        self.rot_0_btn.clicked.connect(lambda: self.canvas.set_rotation(0))
        tb_layout.addWidget(self.rot_0_btn)

        self.rot_90_btn = QtWidgets.QPushButton("90° Landscape")
        self.rot_90_btn.clicked.connect(lambda: self.canvas.set_rotation(90))
        tb_layout.addWidget(self.rot_90_btn)

        self.rot_180_btn = QtWidgets.QPushButton("180°")
        self.rot_180_btn.clicked.connect(lambda: self.canvas.set_rotation(180))
        tb_layout.addWidget(self.rot_180_btn)

        self.rot_270_btn = QtWidgets.QPushButton("270°")
        self.rot_270_btn.clicked.connect(lambda: self.canvas.set_rotation(270))
        tb_layout.addWidget(self.rot_270_btn)

        tb_layout.addSpacing(12)

        # Overlays toggles
        self.cb_safe = QtWidgets.QCheckBox("Safe Areas")
        self.cb_safe.setChecked(True)
        self.cb_safe.toggled.connect(self._on_toggle_safe)
        tb_layout.addWidget(self.cb_safe)

        self.cb_cutouts = QtWidgets.QCheckBox("Cutouts")
        self.cb_cutouts.setChecked(True)
        self.cb_cutouts.toggled.connect(self._on_toggle_cutouts)
        tb_layout.addWidget(self.cb_cutouts)

        self.cb_mask = QtWidgets.QCheckBox("Hinge/Watch Mask")
        self.cb_mask.setChecked(True)
        self.cb_mask.toggled.connect(self._on_toggle_mask)
        tb_layout.addWidget(self.cb_mask)

        self.cb_grid = QtWidgets.QCheckBox("Layout Grid")
        self.cb_grid.setChecked(True)
        self.cb_grid.toggled.connect(self._on_toggle_grid)
        tb_layout.addWidget(self.cb_grid)

        tb_layout.addStretch()

        # Zoom Selector
        tb_layout.addWidget(QtWidgets.QLabel("Zoom:"))
        self.zoom_combo = QtWidgets.QComboBox()
        self.zoom_combo.addItem("Fit Window", 1.0)
        self.zoom_combo.addItem("50%", 0.5)
        self.zoom_combo.addItem("75%", 0.75)
        self.zoom_combo.addItem("100%", 1.0)
        self.zoom_combo.addItem("125%", 1.25)
        self.zoom_combo.currentIndexChanged.connect(self._on_zoom_changed)
        tb_layout.addWidget(self.zoom_combo)

        layout.addLayout(tb_layout)

        # Canvas Area
        self.canvas = ViewportCanvas()
        layout.addWidget(self.canvas, stretch=1)

    def set_profile(self, profile: ScreenProfile) -> None:
        self.canvas.set_profile(profile)
        w_class, h_class = profile.get_window_size_classes()
        self.size_badge.setText(f"Width: {w_class.split()[0]} | Height: {h_class.split()[0]}")

    def _on_toggle_safe(self, checked: bool) -> None:
        self.canvas.show_safe_areas = checked
        self.canvas.update()

    def _on_toggle_cutouts(self, checked: bool) -> None:
        self.canvas.show_cutouts = checked
        self.canvas.update()

    def _on_toggle_mask(self, checked: bool) -> None:
        self.canvas.show_mask = checked
        self.canvas.update()

    def _on_toggle_grid(self, checked: bool) -> None:
        self.canvas.show_grid = checked
        self.canvas.update()

    def _on_zoom_changed(self) -> None:
        val = self.zoom_combo.currentData()
        self.canvas.zoom_factor = float(val)
        self.canvas.update()
