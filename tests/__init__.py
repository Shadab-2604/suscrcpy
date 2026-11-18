"""Test suite package initialization for SUSCRCPY."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

if not QApplication.instance():
    _qt_test_app = QApplication(["suscrcpy_tests", "-platform", "offscreen"])
