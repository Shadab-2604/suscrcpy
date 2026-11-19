"""Dark desktop stylesheet for SUSCRCPY.

Design tokens follow the restrained, layered look of a modern mobile OS: near-black
canvas, softly elevated panels, 8-12 px radii, a single blue accent and colour reserved
for state (connected / warning / error) rather than decoration.
"""
from __future__ import annotations

COLOR_MAIN_BG = "#0D0D0F"
COLOR_PANEL_BG = "#17171A"
COLOR_ELEVATED = "#1F1F23"
COLOR_BORDER = "#2E2E33"
COLOR_TEXT = "#F2F2F7"
COLOR_TEXT_MUTED = "#9A9AA0"
COLOR_ACCENT = "#0A84FF"
COLOR_SUCCESS = "#30D158"
COLOR_WARNING = "#FF9F0A"
COLOR_ERROR = "#FF453A"
COLOR_CRASH = "#FF6961"
COLOR_HOVER = "#2A2A2F"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLOR_MAIN_BG};
    color: {COLOR_TEXT};
    font-family: "SF Pro Text", "Segoe UI", "Noto Sans", Roboto, Arial, sans-serif;
    font-size: 12px;
}}

QToolTip {{
    background-color: {COLOR_ELEVATED};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 8px;
}}

QStatusBar {{
    background-color: {COLOR_PANEL_BG};
    border-top: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_MUTED};
    padding-left: 4px;
}}

/* ---------------------------------------------------------------- header */
QFrame#headerBar {{
    background-color: {COLOR_PANEL_BG};
    border-bottom: 1px solid {COLOR_BORDER};
    min-height: 52px;
    max-height: 52px;
}}

QLabel#brandTitle {{
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1.4px;
}}

QLabel#brandVersion {{
    color: {COLOR_TEXT_MUTED};
    background-color: {COLOR_ELEVATED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 1px 7px;
    font-size: 10px;
}}

QLabel#statusDot {{
    font-weight: 600;
}}

/* --------------------------------------------------------------- layouts */
QSplitter::handle {{ background-color: transparent; }}
QSplitter::handle:horizontal {{ width: 8px; }}

/* ----------------------------------------------------------------- tabs */
QTabWidget#workstationTabs::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    background-color: {COLOR_PANEL_BG};
    top: -1px;
}}

QTabWidget#workstationTabs QTabBar::tab {{
    background: transparent;
    color: {COLOR_TEXT_MUTED};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 7px 18px;
    margin-right: 10px;
    font-weight: 600;
}}

QTabWidget#workstationTabs QTabBar::tab:selected {{
    color: {COLOR_TEXT};
    border-bottom: 2px solid {COLOR_ACCENT};
}}

QTabWidget#workstationTabs QTabBar::tab:hover:!selected {{
    color: {COLOR_TEXT};
}}

/* --------------------------------------------------------------- inputs */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {COLOR_ELEVATED};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 4px 9px;
    min-height: 24px;
    selection-background-color: #1B4B86;
}}

QLineEdit:hover, QSpinBox:hover, QComboBox:hover {{
    border-color: #3F3F46;
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {COLOR_ACCENT};
}}

QComboBox::drop-down {{ border: none; width: 18px; }}

QComboBox QAbstractItemView {{
    background-color: {COLOR_ELEVATED};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    selection-background-color: #1B4B86;
    padding: 4px;
    outline: none;
}}

QCheckBox, QRadioButton {{ color: {COLOR_TEXT}; spacing: 6px; }}

QListWidget {{
    background-color: #111114;
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    outline: none;
}}

QListWidget::item {{ padding: 6px 10px; border-bottom: 1px solid #202024; }}
QListWidget::item:selected {{ background-color: #12385E; color: #FFFFFF; }}
QListWidget::item:hover {{ background-color: {COLOR_HOVER}; }}

/* -------------------------------------------------------------- buttons */
QPushButton {{
    background-color: {COLOR_ELEVATED};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 5px 14px;
    min-height: 24px;
    font-weight: 500;
}}

QPushButton:hover {{ background-color: {COLOR_HOVER}; border-color: #3F3F46; }}
QPushButton:pressed {{ background-color: #17171A; }}
QPushButton:focus {{ border-color: {COLOR_ACCENT}; }}

QPushButton:disabled {{
    background-color: #151518;
    color: #5A5A60;
    border-color: #232327;
}}

QPushButton#primaryBtn {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2B95FF, stop:1 #0A6FE0);
    border: 1px solid #0A6FE0;
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#primaryBtn:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #46A3FF, stop:1 #1479E8);
}}

QPushButton#primaryBtn:disabled {{ background-color: #16243A; color: #6E8199; border-color: #1C2E46; }}

QPushButton#dangerBtn {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF5A4E, stop:1 #D93025);
    border: 1px solid #C42B20;
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#dangerBtn:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF7369, stop:1 #E33B2F);
}}

QPushButton#ghostBtn {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {COLOR_TEXT_MUTED};
    padding: 4px 10px;
}}

QPushButton#ghostBtn:hover {{ color: {COLOR_TEXT}; border-color: {COLOR_BORDER}; background-color: {COLOR_ELEVATED}; }}

QToolButton#ghostBtn {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: {COLOR_TEXT_MUTED};
    padding: 6px 12px;
    font-weight: 500;
}}

QToolButton#ghostBtn:hover {{ color: {COLOR_TEXT}; border-color: {COLOR_BORDER}; background-color: {COLOR_ELEVATED}; }}

QToolButton#subtleBtn {{
    background-color: {COLOR_ELEVATED};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    color: {COLOR_TEXT};
    padding: 6px 13px;
    font-weight: 500;
}}

QToolButton#subtleBtn:hover {{ background-color: {COLOR_HOVER}; border-color: #3F3F46; }}
QToolButton#subtleBtn::menu-indicator {{ image: none; width: 0; }}
QToolButton#ghostBtn::menu-indicator {{ image: none; width: 0; }}

QMenu {{
    background-color: {COLOR_ELEVATED};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 6px;
}}

QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background-color: #12385E; color: #FFFFFF; }}
QMenu::separator {{ height: 1px; background: {COLOR_BORDER}; margin: 5px 8px; }}

/* ------------------------------------------------- segmented control */
QFrame#segmentedControl {{
    background-color: #101013;
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}

QPushButton#segmentBtn {{
    background-color: transparent;
    border: none;
    border-radius: 7px;
    color: {COLOR_TEXT_MUTED};
    padding: 3px 11px;
    min-height: 22px;
    font-weight: 600;
}}

QPushButton#segmentBtn:hover {{ color: {COLOR_TEXT}; }}

QPushButton#segmentBtn:checked {{
    background-color: {COLOR_ELEVATED};
    color: #FFFFFF;
    border: 1px solid #3A3A40;
}}

/* --------------------------------------------------------- mirror pane */
QFrame#mirrorToolbar {{
    background-color: {COLOR_PANEL_BG};
    border-bottom: 1px solid {COLOR_BORDER};
}}

QWidget#viewportCanvas {{ background-color: #050506; }}

QFrame#viewportPlaceholder {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
}}

QLabel#placeholderTitle {{ font-size: 13px; font-weight: 600; color: {COLOR_TEXT}; }}
QLabel#placeholderText {{ color: {COLOR_TEXT_MUTED}; }}

QLabel#waylandBanner {{
    background-color: #2A2415;
    border: 1px solid #6B5522;
    border-radius: 8px;
    color: #E8CE8A;
    padding: 8px;
}}

QLabel#updatingBadge {{
    background-color: #10233A;
    border: 1px solid {COLOR_ACCENT};
    border-radius: 8px;
    color: #9CCBFF;
    padding: 6px 14px;
    font-weight: 600;
}}

QFrame#syncBar {{
    background-color: {COLOR_PANEL_BG};
    border-top: 1px solid {COLOR_BORDER};
}}

QFrame#syncBar QLabel {{ color: {COLOR_TEXT_MUTED}; font-size: 11px; }}
QFrame#syncBar QPushButton {{ font-size: 11px; min-height: 20px; padding: 2px 9px; }}
QLabel#modeBadge {{ color: #7DD3FC; font-weight: 700; letter-spacing: 0.5px; }}
QLabel#syncOk {{ color: {COLOR_SUCCESS}; font-weight: 700; }}
QLabel#syncBad {{ color: {COLOR_WARNING}; font-weight: 700; }}
QLabel#syncIdle {{ color: {COLOR_TEXT_MUTED}; font-weight: 600; }}

/* ---------------------------------------------------------- text labels */
QLabel#inlineLabel {{ color: {COLOR_TEXT_MUTED}; }}
QLabel#mutedLabel {{ color: {COLOR_TEXT_MUTED}; font-size: 11px; }}
QLabel#stateLabel {{ font-size: 14px; font-weight: 600; }}
QLabel#ratioLabel {{ color: #7DD3FC; font-weight: 600; }}

QLabel#noticeLabel {{
    color: {COLOR_TEXT_MUTED};
    font-size: 11px;
}}

QLabel#statCrash {{ color: {COLOR_CRASH}; font-weight: 700; }}
QLabel#statError {{ color: {COLOR_ERROR}; font-weight: 700; }}

QLabel#crashBanner {{
    background-color: #3A1414;
    border: 1px solid {COLOR_CRASH};
    border-radius: 8px;
    color: #FFB4B4;
    font-weight: 700;
    padding: 6px 10px;
}}

/* ---------------------------------------------------------------- logs */
QPlainTextEdit#logView {{
    background-color: #08080A;
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 4px;
    font-family: "JetBrains Mono", "DejaVu Sans Mono", Consolas, monospace;
    font-size: 11px;
    selection-background-color: #1B4B86;
}}

/* ------------------------------------------------------------ scrollbars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3A3A40; min-height: 24px; border-radius: 4px; }}
QScrollBar::handle:vertical:hover {{ background: #505057; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #3A3A40; min-width: 24px; border-radius: 4px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

QMessageBox {{ background-color: {COLOR_PANEL_BG}; }}
QMessageBox QLabel {{ color: {COLOR_TEXT}; }}
"""

DARK_STYLESHEET = STYLESHEET
