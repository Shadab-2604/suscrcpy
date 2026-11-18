"""Network Testing & Proxy Management Panel for SUSCRCPY Workstation.

Configures Android global HTTP/HTTPS debugging proxies (Burp Suite, OWASP ZAP,
mitmproxy), conducts TCP connectivity pre-checks, and provides authorized
security testing workflows.
"""
from __future__ import annotations

import logging
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from core.event_manager import EventManager
from core.proxy_manager import ProxyConfig, ProxyManager

logger = logging.getLogger("suscrcpy.ui.proxy_panel")


class ProxyPanel(QtWidgets.QWidget):
    """Network proxy configuration and security testing diagnostics panel."""

    def __init__(
        self,
        proxy_manager: ProxyManager,
        event_manager: EventManager,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.proxy_mgr = proxy_manager
        self.event_mgr = event_manager
        self._current_serial: Optional[str] = None

        self._build_ui()
        self._connect_signals()

    def set_device_serial(self, serial: Optional[str]) -> None:
        self._current_serial = serial
        self.set_btn.setEnabled(bool(serial))
        self.clear_btn.setEnabled(bool(serial))
        self.refresh_btn.setEnabled(bool(serial))
        if serial:
            self.refresh_status()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Status Banner
        self.status_banner = QtWidgets.QFrame()
        self.status_banner.setStyleSheet("QFrame { background-color: #18202C; border: 1px solid #263345; border-radius: 6px; padding: 12px; }")
        sb_layout = QtWidgets.QVBoxLayout(self.status_banner)
        sb_layout.setContentsMargins(10, 10, 10, 10)

        top_sb = QtWidgets.QHBoxLayout()
        self.status_dot = QtWidgets.QLabel("●")
        self.status_dot.setStyleSheet("color: #8DA2BC; font-size: 16px;")
        self.status_title = QtWidgets.QLabel("Direct Connection (No Proxy)")
        self.status_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #FFF;")
        top_sb.addWidget(self.status_dot)
        top_sb.addWidget(self.status_title)
        top_sb.addStretch()

        self.refresh_btn = QtWidgets.QPushButton("↻ Refresh")
        self.refresh_btn.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        top_sb.addWidget(self.refresh_btn)
        sb_layout.addLayout(top_sb)

        self.status_detail = QtWidgets.QLabel("Device connects directly to network. No inspection proxy configured.")
        self.status_detail.setStyleSheet("color: #8DA2BC; font-size: 11px; margin-top: 4px;")
        sb_layout.addWidget(self.status_detail)

        layout.addWidget(self.status_banner)

        # Proxy Configuration Card
        config_card = QtWidgets.QGroupBox("HTTP Debugging Proxy Settings")
        config_card.setStyleSheet("QGroupBox { font-weight: 600; font-size: 12px; color: #FFF; border: 1px solid #263345; border-radius: 6px; margin-top: 10px; padding: 14px; }")
        cc_layout = QtWidgets.QFormLayout(config_card)
        cc_layout.setSpacing(10)

        self.host_input = QtWidgets.QLineEdit()
        self.host_input.setPlaceholderText("e.g. 192.168.1.100 or 127.0.0.1")
        self.host_input.setText("127.0.0.1")
        cc_layout.addRow("Proxy Host/IP:", self.host_input)

        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8080)
        cc_layout.addRow("Proxy Port:", self.port_input)

        # Action Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(8)

        self.test_btn = QtWidgets.QPushButton("⚡ Test Reachability")
        btn_layout.addWidget(self.test_btn)

        self.set_btn = QtWidgets.QPushButton("Apply Proxy to Device")
        self.set_btn.setStyleSheet("background-color: #3B82F6; color: white; font-weight: 600; padding: 5px 12px; border-radius: 4px;")
        btn_layout.addWidget(self.set_btn)

        self.clear_btn = QtWidgets.QPushButton("Clear Device Proxy")
        self.clear_btn.setStyleSheet("background-color: #EF4444; color: white; font-weight: 600; padding: 5px 12px; border-radius: 4px;")
        btn_layout.addWidget(self.clear_btn)

        cc_layout.addRow("", btn_layout)
        layout.addWidget(config_card)

        # Security Guidance Card
        guide_card = QtWidgets.QGroupBox("Burp Suite / OWASP ZAP Setup Guidance")
        guide_card.setStyleSheet("QGroupBox { font-weight: 600; font-size: 12px; color: #FFF; border: 1px solid #263345; border-radius: 6px; margin-top: 10px; padding: 14px; }")
        g_layout = QtWidgets.QVBoxLayout(guide_card)

        guide_text = QtWidgets.QLabel(
            "<b>1. Configure Proxy Listener:</b> In Burp/ZAP, set Proxy Listener to bind to <i>All interfaces</i> (or your LAN IP) on port 8080.<br>"
            "<b>2. Set Device Proxy:</b> Enter your workstation's LAN IP above and click <i>Apply Proxy to Device</i>.<br>"
            "<b>3. Test Reachability:</b> Click <i>Test Reachability</i> to ensure workstation port is listening and not blocked by firewall.<br>"
            "<b>4. Install CA Certificate (for HTTPS):</b> Export Burp/ZAP CA certificate (DER/CRT), push to device, and install manually via <i>Settings → Security → Encryption & credentials → Install a certificate → CA certificate</i>.<br>"
            "<b>5. Security Compliance:</b> SUSCRCPY enforces local proxy inspection without modifying system trust stores or silently bypassing pinning."
        )
        guide_text.setStyleSheet("color: #8DA2BC; font-size: 11px; line-height: 1.5;")
        guide_text.setWordWrap(True)
        g_layout.addWidget(guide_text)

        layout.addWidget(guide_card)
        layout.addStretch()

    def _connect_signals(self) -> None:
        self.refresh_btn.clicked.connect(self.refresh_status)
        self.test_btn.clicked.connect(self._on_test_connectivity)
        self.set_btn.clicked.connect(self._on_set_proxy)
        self.clear_btn.clicked.connect(self._on_clear_proxy)
        self.proxy_mgr.proxy_status_changed.connect(self._update_ui_state)

    def refresh_status(self) -> None:
        if not self._current_serial:
            return
        self.proxy_mgr.get_device_proxy(self._current_serial)

    def _on_test_connectivity(self) -> None:
        host = self.host_input.text().strip()
        port = self.port_input.value()
        reachable, msg = self.proxy_mgr.test_proxy_connectivity(host, port)
        if reachable:
            QtWidgets.QMessageBox.information(self, "Proxy Reachable", msg)
        else:
            QtWidgets.QMessageBox.warning(self, "Proxy Unreachable", msg)

    def _on_set_proxy(self) -> None:
        if not self._current_serial:
            QtWidgets.QMessageBox.warning(self, "No Device", "Please select an active Android device.")
            return
        host = self.host_input.text().strip()
        port = self.port_input.value()
        ok, msg = self.proxy_mgr.set_device_proxy(self._current_serial, host, port)
        if ok:
            self.event_mgr.record_event(
                category="proxy",
                action="configured",
                description=f"Global HTTP proxy configured to {host}:{port}",
                device_serial=self._current_serial,
                metadata={"host": host, "port": port},
            )
            QtWidgets.QMessageBox.information(self, "Proxy Configured", msg)
        else:
            QtWidgets.QMessageBox.critical(self, "Proxy Error", msg)

    def _on_clear_proxy(self) -> None:
        if not self._current_serial:
            return
        ok, msg = self.proxy_mgr.clear_device_proxy(self._current_serial)
        if ok:
            self.event_mgr.record_event(
                category="proxy",
                action="cleared",
                description="Global HTTP proxy removed (Direct connection restored)",
                device_serial=self._current_serial,
            )
            QtWidgets.QMessageBox.information(self, "Proxy Cleared", msg)
        else:
            QtWidgets.QMessageBox.critical(self, "Proxy Error", msg)

    def _update_ui_state(self, config: ProxyConfig) -> None:
        if config.is_enabled:
            self.status_dot.setText("●")
            self.status_dot.setStyleSheet("color: #10B981; font-size: 16px;")
            self.status_title.setText(f"Proxy Active: {config.host}:{config.port}")
            self.status_detail.setText(config.status_message)
            self.host_input.setText(config.host)
            self.port_input.setValue(config.port)
        else:
            self.status_dot.setText("●")
            self.status_dot.setStyleSheet("color: #8DA2BC; font-size: 16px;")
            self.status_title.setText("Direct Connection (No Proxy)")
            self.status_detail.setText(config.status_message)
