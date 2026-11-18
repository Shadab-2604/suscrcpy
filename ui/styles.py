"""Minimal native desktop utility stylesheet for SUSCRCPY.

Follows the dark charcoal palette and clean native desktop utility styling:
  Main background: #141414
  Panel background: #1D1D1D
  Panel border: #333333
  Primary text: #EEEEEE
  Secondary text: #999999
  Error: #E05252
  Warning: #D9A441
  Success: #65B58A
"""
from __future__ import annotations

COLOR_MAIN_BG = "#141414"
COLOR_PANEL_BG = "#1D1D1D"
COLOR_CARD = "#1D1D1D"
COLOR_BORDER = "#333333"
COLOR_TEXT_PRIMARY = "#EEEEEE"
COLOR_TEXT_SECONDARY = "#999999"
COLOR_TEXT = "#EEEEEE"
COLOR_TEXT_BRIGHT = "#FFFFFF"
COLOR_TEXT_MUTED = "#888888"
COLOR_ACCENT = "#4A90E2"
COLOR_SUCCESS = "#65B58A"
COLOR_WARNING = "#D9A441"
COLOR_ERROR = "#E05252"
COLOR_CRASH = "#FF4444"
COLOR_HOVER = "#2A2A2A"

STYLESHEET = f"""
QMainWindow {{
    background-color: {COLOR_MAIN_BG};
}}

QWidget {{
    background-color: {COLOR_MAIN_BG};
    color: {COLOR_TEXT_PRIMARY};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
}}

/* Header Bar */
QFrame#headerBar {{
    background-color: {COLOR_PANEL_BG};
    border-bottom: 1px solid {COLOR_BORDER};
    min-height: 46px;
    max-height: 52px;
}}

QLabel#brandTitle {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: {COLOR_TEXT_PRIMARY};
}}

/* Panels */
QFrame#panel {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
}}

QGroupBox {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    margin-top: 14px;
    padding: 8px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* Form Controls */
QLineEdit, QSpinBox, QComboBox {{
    background-color: #141414;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: #2F4F75;
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {COLOR_ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: #181818;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: #252525;
    padding: 2px;
}}

/* Push Buttons */
QPushButton {{
    background-color: #252525;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
    padding: 4px 12px;
    min-height: 22px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {COLOR_HOVER};
    border-color: #444444;
}}

QPushButton:pressed {{
    background-color: #1A1A1A;
}}

QPushButton:disabled {{
    background-color: #181818;
    color: #555555;
    border-color: #252525;
}}

QPushButton#primaryBtn {{
    background-color: #1E3A5F;
    border-color: #2D588F;
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#primaryBtn:hover {{
    background-color: #264B7A;
    border-color: {COLOR_ACCENT};
}}

QPushButton#dangerBtn {{
    background-color: #3E1B1B;
    border-color: #612727;
    color: #FFAAAA;
}}

QPushButton#dangerBtn:hover {{
    background-color: #522222;
}}

QPushButton#successBtn {{
    background-color: #1B3828;
    border-color: #2D5A40;
    color: #AAFFAA;
}}

/* Splitters */
QSplitter::handle {{
    background-color: {COLOR_BORDER};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* Log Text Editor */
QPlainTextEdit#logView {{
    background-color: #0F0F0F;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 3px;
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 11px;
    selection-background-color: #2B4565;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: #141414;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: #333333;
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #4A4A4A;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background: #141414;
    height: 8px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: #333333;
    min-width: 20px;
    border-radius: 4px;
}}

/* Status indicator badge */
QLabel#statusDot {{
    font-size: 11px;
    font-weight: 600;
}}
"""

DARK_STYLESHEET = STYLESHEET

