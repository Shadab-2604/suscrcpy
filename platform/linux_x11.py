"""Linux X11 / XWayland native window embedder for SUSCRCPY.

Locates scrcpy native X11 windows and reparents them into the Qt widget container
using Qt QWindow foreign window adoption and createWindowContainer.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from platform.base import BaseWindowEmbedder

logger = logging.getLogger("suscrcpy.platform.linux_x11")


class LinuxX11Embedder(BaseWindowEmbedder):
    """Embeds external X11 windows into Qt container widgets."""

    def is_supported(self) -> bool:
        """Supported when DISPLAY environment variable is set (X11 or XWayland)."""
        return bool(os.environ.get("DISPLAY"))

    def find_window(
        self,
        window_title: str,
        pid: Optional[int] = None,
        timeout: float = 6.0,
    ) -> Optional[int]:
        """Locate the X11 Window ID by exact or regex window title."""
        start_time = time.time()
        pattern = re.compile(rf"{re.escape(window_title)}", re.IGNORECASE)

        while time.time() - start_time < timeout:
            # 1. Try xdotool if installed
            if shutil.which("xdotool"):
                try:
                    res = subprocess.run(
                        ["xdotool", "search", "--name", f"^{window_title}$"],
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=1.5,
                        check=False,
                    )
                    if res.returncode == 0:
                        lines = res.stdout.strip().split()
                        if lines:
                            wid = int(lines[-1])
                            logger.info("Found X11 window %s via xdotool for '%s'", wid, window_title)
                            return wid
                except Exception as e:
                    logger.debug("xdotool search error: %s", e)

            # 2. Try xwininfo -root -tree fallback
            if shutil.which("xwininfo"):
                try:
                    res = subprocess.run(
                        ["xwininfo", "-root", "-tree"],
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=2.0,
                        check=False,
                    )
                    if res.returncode == 0:
                        for line in res.stdout.splitlines():
                            if pattern.search(line):
                                m = re.search(r"0x[0-9a-fA-F]+", line)
                                if m:
                                    wid = int(m.group(0), 16)
                                    logger.info("Found X11 window 0x%x via xwininfo for '%s'", wid, window_title)
                                    return wid
                except Exception as e:
                    logger.debug("xwininfo search error: %s", e)

            time.sleep(0.1)

        logger.warning("Timed out searching for X11 window with title '%s'", window_title)
        return None

    def embed_window(
        self,
        window_id: int,
        parent_widget: QtWidgets.QWidget,
    ) -> Optional[QtWidgets.QWidget]:
        """Reparent foreign X11 window into Qt widget hierarchy."""
        try:
            qwindow = QtGui.QWindow.fromWinId(window_id)
            if not qwindow:
                logger.error("QtGui.QWindow.fromWinId returned None for X11 wid: %d", window_id)
                return None

            container = QtWidgets.QWidget.createWindowContainer(qwindow, parent_widget)
            container.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            container.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
            return container
        except Exception as e:
            logger.error("Failed to embed X11 window %d into Qt container: %s", window_id, e)
            return None
