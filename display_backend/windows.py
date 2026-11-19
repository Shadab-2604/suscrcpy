"""Windows Win32 native window embedder for SUSCRCPY.

Locates scrcpy HWND handles using Win32 user32 APIs, reconfigures child window styles,
and reparents into the Qt container widget using QWindow.fromWinId.
"""
from __future__ import annotations

import logging
import sys
import time
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from display_backend.base import BaseWindowEmbedder

logger = logging.getLogger("suscrcpy.platform.windows")


class WindowsEmbedder(BaseWindowEmbedder):
    """Embeds external Windows HWND windows into Qt container widgets."""

    def is_supported(self) -> bool:
        return sys.platform.startswith("win")

    def find_window(
        self,
        window_title: str,
        pid: Optional[int] = None,
        timeout: float = 6.0,
    ) -> Optional[int]:
        """Locate the HWND of the scrcpy window matching title and PID."""
        if not self.is_supported():
            return None

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        start_time = time.time()

        while time.time() - start_time < timeout:
            # First attempt direct FindWindowW
            hwnd = user32.FindWindowW(None, window_title)
            if hwnd:
                if pid is not None:
                    proc_id = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
                    if proc_id.value == pid:
                        logger.info("Found HWND 0x%x for PID %d and title '%s'", hwnd, pid, window_title)
                        return hwnd
                else:
                    return hwnd

            # Fallback: enumerate top-level windows
            found_hwnd = None

            def enum_proc(h: int, lparam: int) -> bool:
                nonlocal found_hwnd
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(h, buffer, length + 1)
                    if window_title in buffer.value:
                        if pid is not None:
                            proc_id = wintypes.DWORD()
                            user32.GetWindowThreadProcessId(h, ctypes.byref(proc_id))
                            if proc_id.value == pid:
                                found_hwnd = h
                                return False
                        else:
                            found_hwnd = h
                            return False
                return True

            enum_func_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            c_enum_proc = enum_func_type(enum_proc)
            user32.EnumWindows(c_enum_proc, 0)

            if found_hwnd:
                logger.info("Found HWND 0x%x via EnumWindows for '%s'", found_hwnd, window_title)
                return found_hwnd

            time.sleep(0.1)

        logger.warning("Timed out searching for Windows HWND for '%s'", window_title)
        return None

    def embed_window(
        self,
        window_id: int,
        parent_widget: QtWidgets.QWidget,
    ) -> Optional[QtWidgets.QWidget]:
        """Reconfigure Win32 child styles and embed into Qt container."""
        if not self.is_supported():
            return None

        import ctypes

        user32 = ctypes.windll.user32

        GWL_STYLE = -16
        WS_CHILD = 0x40000000
        WS_POPUP = 0x80000000
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000

        try:
            # Adjust window style to be a child window without borders
            style = user32.GetWindowLongW(window_id, GWL_STYLE)
            style = (style & ~WS_POPUP & ~WS_CAPTION & ~WS_THICKFRAME & ~WS_MINIMIZEBOX & ~WS_MAXIMIZEBOX) | WS_CHILD
            user32.SetWindowLongW(window_id, GWL_STYLE, style)

            parent_hwnd = int(parent_widget.winId())
            user32.SetParent(window_id, parent_hwnd)

            qwindow = QtGui.QWindow.fromWinId(window_id)
            if not qwindow:
                logger.error("QtGui.QWindow.fromWinId returned None for HWND: 0x%x", window_id)
                return None

            container = QtWidgets.QWidget.createWindowContainer(qwindow, parent_widget)
            container.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            container.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            return container
        except Exception as e:
            logger.error("Failed to embed HWND 0x%x into Qt container: %s", window_id, e)
            return None
