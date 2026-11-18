"""Screenshot Review & Annotation Dialog for SUSCRCPY Workstation.

Provides preview, non-destructive annotation tools (Rectangle, Arrow, Text,
and Redaction/Blur), and single-click saving of the annotated copy.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets

from core.screenshot_manager import ScreenshotManager, ScreenshotMetadata

logger = logging.getLogger("suscrcpy.ui.screenshot_dialog")


class AnnotationCanvas(QtWidgets.QLabel):
    """Interactive canvas widget allowing testers to draw boxes, arrows, text, and blurs."""

    def __init__(self, raw_pixmap: QtGui.QPixmap, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.raw_pixmap = raw_pixmap
        self.setPixmap(self.raw_pixmap)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)

        self.current_tool: str = "box"  # "box", "arrow", "text", "blur"
        self.current_color = QtGui.QColor("#EF4444")  # red default
        self.pen_width = 3

        self.rectangles: List[Tuple[QtCore.QRect, QtGui.QColor, int]] = []
        self.arrows: List[Tuple[QtCore.QPoint, QtCore.QPoint, QtGui.QColor, int]] = []
        self.texts: List[Tuple[QtCore.QPoint, str, QtGui.QColor, int]] = []
        self.blurs: List[QtCore.QRect] = []

        self._drawing = False
        self._start_pos: Optional[QtCore.QPoint] = None
        self._current_pos: Optional[QtCore.QPoint] = None

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drawing = True
            self._start_pos = event.position().toPoint()
            self._current_pos = self._start_pos

            if self.current_tool == "text":
                text, ok = QtWidgets.QInputDialog.getText(
                    self, "Add Annotation Text", "Enter label text:"
                )
                if ok and text:
                    self.texts.append((self._start_pos, text, self.current_color, 14))
                    self._drawing = False
                    self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drawing:
            self._current_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            end_pos = event.position().toPoint()
            if self._start_pos:
                rect = QtCore.QRect(self._start_pos, end_pos).normalized()
                if self.current_tool == "box":
                    self.rectangles.append((rect, self.current_color, self.pen_width))
                elif self.current_tool == "arrow":
                    self.arrows.append((self._start_pos, end_pos, self.current_color, self.pen_width))
                elif self.current_tool == "blur":
                    self.blurs.append(rect)
            self._start_pos = None
            self._current_pos = None
            self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        # Draw existing annotations
        for rect, color, w in self.rectangles:
            painter.setPen(QtGui.QPen(color, w))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

        for start, end, color, w in self.arrows:
            ScreenshotManager._draw_arrow(painter, start, end, color, w)

        for pos, text, color, font_size in self.texts:
            painter.setFont(QtGui.QFont("Sans-Serif", font_size, QtGui.QFont.Weight.Bold))
            painter.setPen(color)
            painter.drawText(pos, text)

        for rect in self.blurs:
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 180)))
            painter.drawRect(rect)

        # Draw live drag feedback
        if self._drawing and self._start_pos and self._current_pos:
            painter.setPen(QtGui.QPen(self.current_color, 2, QtCore.Qt.PenStyle.DashLine))
            if self.current_tool == "box":
                painter.drawRect(QtCore.QRect(self._start_pos, self._current_pos).normalized())
            elif self.current_tool == "arrow":
                painter.drawLine(self._start_pos, self._current_pos)
            elif self.current_tool == "blur":
                painter.fillRect(QtCore.QRect(self._start_pos, self._current_pos).normalized(), QtGui.QColor(0, 0, 0, 140))


class ScreenshotDialog(QtWidgets.QDialog):
    """Modal dialog displaying the captured device screenshot with annotation tools."""

    def __init__(
        self,
        screenshot_meta: ScreenshotMetadata,
        screenshot_mgr: ScreenshotManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.meta = screenshot_meta
        self.mgr = screenshot_mgr

        self.setWindowTitle(f"Screenshot Evidence — {Path(self.meta.raw_path).name}")
        self.resize(850, 750)
        self.setStyleSheet("background-color: #12161F; color: #EEEEEE;")

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Toolbar
        tb_layout = QtWidgets.QHBoxLayout()
        tb_layout.setSpacing(8)

        lbl = QtWidgets.QLabel("Annotation Tool:")
        lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #8DA2BC;")
        tb_layout.addWidget(lbl)

        self.tool_grp = QtWidgets.QButtonGroup(self)

        self.box_btn = QtWidgets.QPushButton("▢ Box")
        self.box_btn.setCheckable(True)
        self.box_btn.setChecked(True)
        self.tool_grp.addButton(self.box_btn)
        tb_layout.addWidget(self.box_btn)

        self.arrow_btn = QtWidgets.QPushButton("→ Arrow")
        self.arrow_btn.setCheckable(True)
        self.tool_grp.addButton(self.arrow_btn)
        tb_layout.addWidget(self.arrow_btn)

        self.text_btn = QtWidgets.QPushButton("T Text")
        self.text_btn.setCheckable(True)
        self.tool_grp.addButton(self.text_btn)
        tb_layout.addWidget(self.text_btn)

        self.blur_btn = QtWidgets.QPushButton("▨ Blur/Redact")
        self.blur_btn.setCheckable(True)
        self.tool_grp.addButton(self.blur_btn)
        tb_layout.addWidget(self.blur_btn)

        tb_layout.addSpacing(16)

        color_lbl = QtWidgets.QLabel("Color:")
        color_lbl.setStyleSheet("font-size: 11px; color: #8DA2BC;")
        tb_layout.addWidget(color_lbl)

        self.color_combo = QtWidgets.QComboBox()
        self.color_combo.addItems(["Red", "Yellow", "Cyan", "Green", "White"])
        tb_layout.addWidget(self.color_combo)

        tb_layout.addStretch()

        self.clear_btn = QtWidgets.QPushButton("Clear Annotations")
        tb_layout.addWidget(self.clear_btn)

        layout.addLayout(tb_layout)

        # Canvas Scroll Area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #0B0E14; border: 1px solid #263345;")

        pixmap = QtGui.QPixmap(self.meta.raw_path)
        self.canvas = AnnotationCanvas(pixmap)
        scroll.setWidget(self.canvas)
        layout.addWidget(scroll, 1)

        # Bottom Actions
        bottom_layout = QtWidgets.QHBoxLayout()
        info_str = f"Dimensions: {self.meta.width}x{self.meta.height} | File: {Path(self.meta.raw_path).name}"
        info_lbl = QtWidgets.QLabel(info_str)
        info_lbl.setStyleSheet("color: #8DA2BC; font-size: 11px;")
        bottom_layout.addWidget(info_lbl)

        bottom_layout.addStretch()

        self.save_btn = QtWidgets.QPushButton("💾 Save Annotated Copy")
        self.save_btn.setStyleSheet("background-color: #3B82F6; color: white; padding: 6px 14px; font-weight: 600; border-radius: 4px;")
        bottom_layout.addWidget(self.save_btn)

        self.close_btn = QtWidgets.QPushButton("Close")
        bottom_layout.addWidget(self.close_btn)

        layout.addLayout(bottom_layout)

        # Connections
        self.box_btn.clicked.connect(lambda: setattr(self.canvas, "current_tool", "box"))
        self.arrow_btn.clicked.connect(lambda: setattr(self.canvas, "current_tool", "arrow"))
        self.text_btn.clicked.connect(lambda: setattr(self.canvas, "current_tool", "text"))
        self.blur_btn.clicked.connect(lambda: setattr(self.canvas, "current_tool", "blur"))
        self.color_combo.currentTextChanged.connect(self._on_color_changed)
        self.clear_btn.clicked.connect(self._clear_annotations)
        self.save_btn.clicked.connect(self._save_annotations)
        self.close_btn.clicked.connect(self.accept)

    def _on_color_changed(self, color_name: str) -> None:
        colors = {
            "Red": QtGui.QColor("#EF4444"),
            "Yellow": QtGui.QColor("#F59E0B"),
            "Cyan": QtGui.QColor("#06B6D4"),
            "Green": QtGui.QColor("#10B981"),
            "White": QtGui.QColor("#FFFFFF"),
        }
        self.canvas.current_color = colors.get(color_name, QtGui.QColor("#EF4444"))

    def _clear_annotations(self) -> None:
        self.canvas.rectangles.clear()
        self.canvas.arrows.clear()
        self.canvas.texts.clear()
        self.canvas.blurs.clear()
        self.canvas.update()

    def _save_annotations(self) -> None:
        annotated_path = self.mgr.annotate_screenshot(
            self.meta,
            rectangles=self.canvas.rectangles,
            arrows=self.canvas.arrows,
            texts=self.canvas.texts,
            blur_regions=self.canvas.blurs,
        )
        if annotated_path:
            QtWidgets.QMessageBox.information(
                self, "Annotation Saved",
                f"Annotated screenshot saved successfully to:\n{annotated_path.name}"
            )
            self.accept()
