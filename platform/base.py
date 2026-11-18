"""Abstract window embedding interface for SUSCRCPY."""
from __future__ import annotations

import abc
from typing import Optional, Tuple

from PySide6 import QtWidgets


class BaseWindowEmbedder(abc.ABC):
    """Abstract base class for operating system specific window embedding."""

    @abc.abstractmethod
    def is_supported(self) -> bool:
        """Check if native embedding is supported in the current environment."""
        pass

    @abc.abstractmethod
    def find_window(
        self,
        window_title: str,
        pid: Optional[int] = None,
        timeout: float = 6.0,
    ) -> Optional[int]:
        """Find the native window identifier (HWND or X11 WId) for the given title/PID."""
        pass

    @abc.abstractmethod
    def embed_window(
        self,
        window_id: int,
        parent_widget: QtWidgets.QWidget,
    ) -> Optional[QtWidgets.QWidget]:
        """Reparent and embed the native window into the parent Qt widget container.

        Returns the container widget wrapping the embedded window, or None on failure.
        """
        pass
