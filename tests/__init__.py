"""Test suite package initialization for SUSCRCPY."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication

if not QGuiApplication.instance():
    _qt_test_app = QGuiApplication(["suscrcpy_tests", "-platform", "offscreen"])
