"""Wayland session detection and diagnostics for SUSCRCPY.

Detects Wayland compositor environments, evaluates XWayland bridge capability,
and provides clear explanations and fallbacks without false embedding claims.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Optional

from PySide6 import QtGui

logger = logging.getLogger("suscrcpy.platform.wayland")


@dataclass
class WaylandDiagnostics:
    """Diagnostic details regarding the active Wayland session."""
    is_wayland: bool
    wayland_display: Optional[str]
    x11_display: Optional[str]
    qpa_platform: str
    native_embedding_supported: bool
    guidance_message: str


class WaylandHelper:
    """Diagnostics and helper utilities for Wayland desktop environments."""

    @staticmethod
    def is_wayland_session() -> bool:
        """Detect whether the current user desktop session is Wayland-based."""
        if not sys.platform.startswith("linux"):
            return False
        xdg_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        wayland_disp = os.environ.get("WAYLAND_DISPLAY", "")
        return xdg_type == "wayland" or bool(wayland_disp)

    @staticmethod
    def get_diagnostics() -> WaylandDiagnostics:
        """Evaluate session capabilities and determine embedding feasibility."""
        is_wayland = WaylandHelper.is_wayland_session()
        wayland_display = os.environ.get("WAYLAND_DISPLAY")
        x11_display = os.environ.get("DISPLAY")

        try:
            qpa = QtGui.QGuiApplication.platformName()
        except Exception:
            qpa = "unknown"

        # Native embedding works via XWayland if DISPLAY is set and Qt is running with xcb platform plugin
        if is_wayland:
            if qpa == "xcb" and x11_display:
                supported = True
                msg = (
                    "Wayland session running with XWayland bridge (QT_QPA_PLATFORM=xcb). "
                    "Native scrcpy window embedding is fully supported."
                )
            else:
                supported = False
                msg = (
                    "Wayland compositor detected (Pure Wayland QPA). Native cross-process "
                    "window reparenting is restricted by the Wayland security model.\n\n"
                    "scrcpy is running in a synchronized external companion window.\n\n"
                    "Tip: To enable embedded display mode on Wayland, start SUSCRCPY with:\n"
                    "    QT_QPA_PLATFORM=xcb suscrcpy"
                )
        else:
            supported = bool(x11_display)
            msg = "X11 session active. Native window embedding is fully supported."

        return WaylandDiagnostics(
            is_wayland=is_wayland,
            wayland_display=wayland_display,
            x11_display=x11_display,
            qpa_platform=qpa,
            native_embedding_supported=supported,
            guidance_message=msg,
        )
