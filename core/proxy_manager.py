"""Network Testing & Proxy Manager for SUSCRCPY.

Coordinates inspection and configuration of Android global HTTP/HTTPS debugging
proxies (e.g. Burp Suite, OWASP ZAP, mitmproxy) for authorized API & security testing.
"""
from __future__ import annotations

import logging
import socket
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from core.adb_manager import AdbManager

logger = logging.getLogger("suscrcpy.proxy_manager")


@dataclass
class ProxyConfig:
    """Represents HTTP proxy configuration on an Android device."""
    host: str = ""
    port: int = 8080
    is_enabled: bool = False
    is_reachable: Optional[bool] = None
    status_message: str = "Not configured"
    last_tested: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProxyManager(QObject):
    """Manages reading, setting, testing, and clearing device proxy configurations."""

    proxy_status_changed = Signal(object)  # ProxyConfig
    connectivity_tested = Signal(bool, str)  # is_reachable, message

    def __init__(self, adb_manager: AdbManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.adb = adb_manager
        self._current_config = ProxyConfig()

    @property
    def current_config(self) -> ProxyConfig:
        return self._current_config

    def get_device_proxy(self, serial: str) -> ProxyConfig:
        """Query Android global settings for the active HTTP proxy."""
        try:
            raw = self.adb.run(["shell", "settings", "get", "global", "http_proxy"], serial=serial).strip()
            if raw and raw not in ("null", ":0", "0.0.0.0:0"):
                if ":" in raw:
                    parts = raw.split(":", 1)
                    host = parts[0]
                    try:
                        port = int(parts[1])
                    except ValueError:
                        port = 8080
                    self._current_config = ProxyConfig(
                        host=host,
                        port=port,
                        is_enabled=True,
                        status_message=f"Proxy configured: {raw}",
                    )
                else:
                    self._current_config = ProxyConfig(
                        host=raw,
                        port=8080,
                        is_enabled=True,
                        status_message=f"Proxy configured: {raw}",
                    )
            else:
                self._current_config = ProxyConfig(
                    is_enabled=False,
                    status_message="No global proxy configured (Direct connection)",
                )
        except Exception as e:
            logger.warning("Failed to query device proxy on %s: %s", serial, e)
            self._current_config = ProxyConfig(
                is_enabled=False,
                status_message=f"Unable to read proxy: {e}",
            )

        self.proxy_status_changed.emit(self._current_config)
        return self._current_config

    def set_device_proxy(self, serial: str, host: str, port: int) -> Tuple[bool, str]:
        """Configure global HTTP proxy on the device via ADB settings."""
        clean_host = host.strip()
        if not clean_host:
            return False, "Proxy host cannot be empty"
        if not (1 <= port <= 65535):
            return False, f"Invalid port {port}. Must be between 1 and 65535."

        proxy_str = f"{clean_host}:{port}"
        try:
            self.adb.run(["shell", "settings", "put", "global", "http_proxy", proxy_str], serial=serial)
            logger.info("Configured device proxy %s on %s", proxy_str, serial)
            self._current_config = ProxyConfig(
                host=clean_host,
                port=port,
                is_enabled=True,
                status_message=f"Proxy set to {proxy_str}",
            )
            self.proxy_status_changed.emit(self._current_config)
            return True, f"Global HTTP proxy configured to {proxy_str}"
        except Exception as e:
            logger.error("Failed to set proxy %s on %s: %s", proxy_str, serial, e)
            return False, f"Error configuring proxy: {e}"

    def clear_device_proxy(self, serial: str) -> Tuple[bool, str]:
        """Disable and remove global HTTP proxy from the device."""
        try:
            self.adb.run(["shell", "settings", "put", "global", "http_proxy", ":0"], serial=serial)
            self.adb.run(["shell", "settings", "delete", "global", "http_proxy"], serial=serial)
            self.adb.run(["shell", "settings", "delete", "global", "global_http_proxy_host"], serial=serial)
            self.adb.run(["shell", "settings", "delete", "global", "global_http_proxy_port"], serial=serial)
            logger.info("Cleared device proxy on %s", serial)
            self._current_config = ProxyConfig(
                is_enabled=False,
                status_message="Direct connection (Proxy removed)",
            )
            self.proxy_status_changed.emit(self._current_config)
            return True, "Global proxy cleared. Device using direct connection."
        except Exception as e:
            logger.error("Failed to clear proxy on %s: %s", serial, e)
            return False, f"Error clearing proxy: {e}"

    def test_proxy_connectivity(self, host: str, port: int, timeout_sec: float = 2.5) -> Tuple[bool, str]:
        """Test whether the proxy endpoint is actively listening on TCP socket."""
        clean_host = host.strip()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_sec)
            result = sock.connect_ex((clean_host, port))
            sock.close()
            now_iso = datetime.now().isoformat()

            if result == 0:
                msg = f"Proxy listener active and reachable at {clean_host}:{port}"
                self._current_config.is_reachable = True
                self._current_config.last_tested = now_iso
                self._current_config.status_message = msg
                self.connectivity_tested.emit(True, msg)
                self.proxy_status_changed.emit(self._current_config)
                return True, msg
            else:
                msg = f"Cannot reach proxy at {clean_host}:{port} (Connection refused or host unreachable)"
                self._current_config.is_reachable = False
                self._current_config.last_tested = now_iso
                self._current_config.status_message = msg
                self.connectivity_tested.emit(False, msg)
                self.proxy_status_changed.emit(self._current_config)
                return False, msg
        except Exception as e:
            msg = f"Connectivity check failed: {e}"
            self._current_config.is_reachable = False
            self._current_config.status_message = msg
            self.connectivity_tested.emit(False, msg)
            self.proxy_status_changed.emit(self._current_config)
            return False, msg
