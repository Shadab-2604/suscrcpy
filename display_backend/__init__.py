"""Platform-specific window embedding adapters for SUSCRCPY."""
from __future__ import annotations

import os
import sys
from typing import Optional

from display_backend.base import BaseWindowEmbedder
from display_backend.linux_wayland import WaylandHelper
from display_backend.linux_x11 import LinuxX11Embedder
from display_backend.windows import WindowsEmbedder


def get_window_embedder() -> Optional[BaseWindowEmbedder]:
    """Return the appropriate window embedder for the current operating system."""
    if sys.platform.startswith("win"):
        return WindowsEmbedder()
    elif sys.platform.startswith("linux"):
        # If DISPLAY is available (X11 or XWayland), use LinuxX11Embedder
        if os.environ.get("DISPLAY"):
            return LinuxX11Embedder()
        # Pure headless or unsupported
        return None
    return None


__all__ = [
    "BaseWindowEmbedder",
    "LinuxX11Embedder",
    "WindowsEmbedder",
    "WaylandHelper",
    "get_window_embedder",
]
