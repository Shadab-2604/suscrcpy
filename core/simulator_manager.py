"""Simulator Integration Manager for SUSCRCPY 2.1.

Coordinates Android Emulator (AVD) and Apple Xcode Simulator execution,
strictly distinguishing physical hardware, virtual simulators, and layout previews.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from core.adb_manager import AdbManager
from core.process_manager import ProcessManager

logger = logging.getLogger("suscrcpy.simulator_manager")


@dataclass
class SimulatorDevice:
    name: str
    platform: str  # "android" or "apple"
    device_type: str  # "phone", "tablet", "foldable", "wearos", "tv"
    status: str  # "stopped", "running", "unsupported"
    target_api: str = "Unknown"
    details: Optional[str] = None


class SimulatorManager(QObject):
    """Manages discovery and launching of platform-specific external simulators."""

    avds_loaded = Signal(list)  # List[SimulatorDevice]
    simulator_launched = Signal(str)  # name
    simulator_stopped = Signal(str)

    def __init__(self, adb_manager: AdbManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.adb = adb_manager
        self._emulator_path = self._locate_emulator()

    def _locate_emulator(self) -> Optional[str]:
        """Locate the Android SDK emulator binary."""
        which_emu = shutil.which("emulator")
        if which_emu:
            return which_emu

        # Check Android SDK path candidates
        candidates = [
            os.path.expanduser("~/Android/Sdk/emulator/emulator"),
            os.path.expanduser("~/Android/Sdk/tools/emulator"),
            "/usr/lib/android-sdk/emulator/emulator",
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    @property
    def is_android_emulator_available(self) -> bool:
        return self._emulator_path is not None

    @property
    def is_apple_simulator_supported(self) -> bool:
        """Xcode simulator is only supported natively on macOS."""
        return sys.platform == "darwin" and shutil.which("xcrun") is not None

    def list_android_avds(self) -> List[SimulatorDevice]:
        """Query available Android Virtual Devices (AVDs)."""
        if not self._emulator_path:
            return []

        try:
            res = subprocess.run(
                [self._emulator_path, "-list-avds"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=6.0,
                check=False,
            )
            avds: List[SimulatorDevice] = []
            for line in res.stdout.splitlines():
                name = line.strip()
                if not name:
                    continue
                # Guess device type from name
                name_l = name.lower()
                dev_type = "phone"
                if "tablet" in name_l:
                    dev_type = "tablet"
                elif "fold" in name_l:
                    dev_type = "foldable"
                elif "wear" in name_l or "watch" in name_l:
                    dev_type = "wearos"
                elif "tv" in name_l:
                    dev_type = "tv"

                avds.append(
                    SimulatorDevice(
                        name=name,
                        platform="android",
                        device_type=dev_type,
                        status="stopped",
                    )
                )
            return avds
        except Exception as e:
            logger.error("Failed to list Android AVDs: %s", e)
            return []

    def launch_android_avd(self, avd_name: str) -> bool:
        """Launch an Android Virtual Device in the background."""
        if not self._emulator_path:
            raise RuntimeError("Android emulator executable not found in system or Android SDK.")

        cmd = [self._emulator_path, "-avd", avd_name]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            ProcessManager.instance().register(proc)
            self.simulator_launched.emit(avd_name)
            return True
        except Exception as e:
            logger.error("Failed to start AVD %s: %s", avd_name, e)
            raise

    def get_apple_support_notice(self) -> str:
        """Return clear explanation regarding Apple simulator compatibility on host OS."""
        if self.is_apple_simulator_supported:
            return "Apple Xcode Simulator is supported on this macOS workstation."
        return (
            "Apple Xcode Simulator requires macOS and Xcode Command Line Tools.\n\n"
            "iOS, iPadOS, watchOS, and tvOS simulators cannot be executed natively on "
            f"{'Linux' if sys.platform.startswith('linux') else 'Windows'}.\n\n"
            "To test iPhone, iPad, and Apple Watch user interfaces on this system, "
            "use 'Mode 2: Screen Profile Preview', which renders authentic device viewports, "
            "safe areas, and Dynamic Island cutouts."
        )
