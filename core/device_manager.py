"""Device state and lifecycle manager for SUSCRCPY.

Coordinates connected devices, active selection, status transitions, and disconnection handling.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from core.adb_manager import AdbDeviceError, AdbError, AdbManager, DeviceDetails, DeviceItem

logger = logging.getLogger("suscrcpy.device_manager")


class ConnectionState(str, Enum):
    CONNECTED = "Connected"
    CONNECTING = "Connecting"
    UNAUTHORIZED = "Unauthorized"
    OFFLINE = "Offline"
    DISCONNECTED = "Disconnected"
    RECONNECTING = "Reconnecting"


class DeviceManager(QObject):
    """Manages multi-device discovery, active device selection, and connection state changes."""

    devices_updated = Signal(list)  # list of DeviceItem
    selected_device_changed = Signal(object)  # DeviceDetails or None
    status_changed = Signal(str, str)  # serial, ConnectionState value
    device_disconnected = Signal(str)  # serial

    def __init__(self, adb_manager: AdbManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.adb = adb_manager
        self._selected_serial: Optional[str] = None
        self._current_details: Optional[DeviceDetails] = None
        self._devices_cache: List[DeviceItem] = []
        self._current_state = ConnectionState.DISCONNECTED

    @property
    def selected_serial(self) -> Optional[str]:
        return self._selected_serial

    @property
    def current_details(self) -> Optional[DeviceDetails]:
        return self._current_details

    @property
    def current_state(self) -> ConnectionState:
        return self._current_state

    def refresh_devices(self) -> List[DeviceItem]:
        """Scan for connected devices and update state."""
        devices = self.adb.list_devices()
        self._devices_cache = devices
        self.devices_updated.emit(devices)

        # Check status of currently selected device
        if self._selected_serial:
            matching = next((d for d in devices if d.serial == self._selected_serial), None)
            if not matching:
                logger.warning("Selected device %s was disconnected.", self._selected_serial)
                old_serial = self._selected_serial
                self._current_state = ConnectionState.DISCONNECTED
                self.device_disconnected.emit(old_serial)
                self.status_changed.emit(old_serial, ConnectionState.DISCONNECTED.value)
            elif not matching.is_authorized:
                self._current_state = ConnectionState.UNAUTHORIZED
                self.status_changed.emit(self._selected_serial, ConnectionState.UNAUTHORIZED.value)
            else:
                if self._current_state != ConnectionState.CONNECTED:
                    self._current_state = ConnectionState.CONNECTED
                    self.status_changed.emit(self._selected_serial, ConnectionState.CONNECTED.value)
        elif devices:
            # Auto-select first authorized device if none is selected
            authorized = [d for d in devices if d.is_authorized]
            if authorized:
                self.select_device(authorized[0].serial)
            else:
                self.select_device(devices[0].serial)

        return devices

    def select_device(self, serial: str) -> Optional[DeviceDetails]:
        """Switch active target device and fetch its diagnostics."""
        self._selected_serial = serial
        matching = next((d for d in self._devices_cache if d.serial == serial), None)

        if not matching:
            self._current_state = ConnectionState.DISCONNECTED
            self._current_details = None
            self.status_changed.emit(serial, ConnectionState.DISCONNECTED.value)
            self.selected_device_changed.emit(None)
            return None

        if not matching.is_authorized:
            self._current_state = ConnectionState.UNAUTHORIZED
            self._current_details = None
            self.status_changed.emit(serial, ConnectionState.UNAUTHORIZED.value)
            self.selected_device_changed.emit(None)
            return None

        self._current_state = ConnectionState.CONNECTING
        self.status_changed.emit(serial, ConnectionState.CONNECTING.value)

        try:
            details = self.adb.get_device_details(serial)
            self._current_details = details
            self._current_state = ConnectionState.CONNECTED
            self.status_changed.emit(serial, ConnectionState.CONNECTED.value)
            self.selected_device_changed.emit(details)
            return details
        except Exception as e:
            logger.error("Failed to fetch device details for %s: %s", serial, e)
            self._current_state = ConnectionState.OFFLINE
            self._current_details = None
            self.status_changed.emit(serial, ConnectionState.OFFLINE.value)
            self.selected_device_changed.emit(None)
            return None
