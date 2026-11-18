"""ADB (Android Debug Bridge) Management for SUSCRCPY.

Handles device discovery, command execution with device serial targeting,
hardware and system diagnostics, resolution adjustments, and log streaming.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("suscrcpy.adb_manager")


class AdbError(RuntimeError):
    """Base exception for ADB operations."""
    pass


class AdbNotFoundError(AdbError):
    """Raised when the ADB binary cannot be located."""
    pass


class AdbTimeoutError(AdbError):
    """Raised when an ADB command times out."""
    pass


class AdbDeviceError(AdbError):
    """Raised when a specific device error occurs (unauthorized, offline, etc.)."""
    pass


@dataclass
class DeviceItem:
    """Represents a connected Android device."""
    serial: str
    status: str  # 'device', 'unauthorized', 'offline', etc.
    model: str = "Unknown"
    product: str = "Unknown"
    device_name: str = "Unknown"
    transport_id: str = ""

    @property
    def is_authorized(self) -> bool:
        return self.status == "device"

    @property
    def is_usb(self) -> bool:
        return ":" not in self.serial


@dataclass
class DeviceDetails:
    """Detailed hardware and software specs of an Android device."""
    serial: str
    manufacturer: str
    model: str
    android_version: str
    sdk_level: str
    cpu_abi: str
    physical_resolution: Tuple[int, int]
    override_resolution: Optional[Tuple[int, int]]
    density: Optional[int]
    storage_free: str
    ram_info: str
    connection_type: str  # USB or TCP/IP


class AdbManager:
    """Manages all interactions with the Android Debug Bridge."""

    def __init__(self, custom_adb_path: Optional[str] = None) -> None:
        self._custom_adb_path = custom_adb_path
        self._adb_path = self.locate_adb()

    def set_custom_adb_path(self, path: Optional[str]) -> None:
        """Set a user-specified custom path to the ADB binary."""
        self._custom_adb_path = path
        self._adb_path = self.locate_adb()

    @property
    def adb_path(self) -> str:
        return self._adb_path

    def locate_adb(self) -> str:
        """Find the ADB executable across standard and configured locations."""
        if self._custom_adb_path and os.path.isfile(self._custom_adb_path):
            return self._custom_adb_path

        env_adb = os.environ.get("ADB_PATH")
        if env_adb and os.path.isfile(env_adb):
            return env_adb

        which_adb = shutil.which("adb")
        if which_adb:
            return which_adb

        # Candidate paths for Linux
        linux_candidates = [
            os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            "/opt/android-sdk/platform-tools/adb",
        ]
        # Candidate paths for Windows
        win_candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\scrcpy\adb.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\scrcpy\adb.exe"),
            r"C:\scrcpy\adb.exe",
            r"C:\platform-tools\adb.exe",
        ]

        candidates = win_candidates if sys.platform.startswith("win") else linux_candidates
        for candidate in candidates:
            if os.path.isfile(candidate) and (sys.platform.startswith("win") or os.access(candidate, os.X_OK)):
                return candidate

        return "adb"  # Fallback to PATH lookup

    def run(
        self,
        args: List[str],
        serial: Optional[str] = None,
        timeout: float = 12.0,
        check_device: bool = True,
    ) -> subprocess.CompletedProcess:
        """Execute an ADB command securely without shell interpolation."""
        cmd = [self._adb_path]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as e:
            raise AdbNotFoundError(f"ADB executable not found at '{self._adb_path}'.") from e
        except subprocess.TimeoutExpired as e:
            raise AdbTimeoutError(f"ADB command timed out after {timeout}s: {' '.join(cmd)}") from e

        if check_device and serial and result.returncode != 0:
            stderr = result.stderr or ""
            if "device unauthorized" in stderr.lower():
                raise AdbDeviceError("Device unauthorized. Unlock device and accept RSA debugging prompt.")
            if "device offline" in stderr.lower():
                raise AdbDeviceError("Device is offline. Check USB cable and device state.")
            if "device not found" in stderr.lower():
                raise AdbDeviceError("Device not found. Verify USB connection.")

        return result

    def start_server(self) -> bool:
        """Start the ADB server if not already running."""
        try:
            res = self.run(["start-server"], timeout=10.0, check_device=False)
            return res.returncode == 0
        except Exception as e:
            logger.warning("Failed to start ADB server: %s", e)
            return False

    def list_devices(self) -> List[DeviceItem]:
        """Discover all connected Android devices with status and model."""
        self.start_server()
        try:
            res = self.run(["devices", "-l"], timeout=8.0, check_device=False)
        except AdbError as e:
            logger.error("Error listing ADB devices: %s", e)
            return []

        devices: List[DeviceItem] = []
        lines = res.stdout.strip().splitlines()
        # Skip header: "List of devices attached"
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue

            serial = parts[0]
            status = parts[1]

            item = DeviceItem(serial=serial, status=status)
            for part in parts[2:]:
                if part.startswith("model:"):
                    item.model = part.split(":", 1)[1]
                elif part.startswith("product:"):
                    item.product = part.split(":", 1)[1]
                elif part.startswith("device:"):
                    item.device_name = part.split(":", 1)[1]
                elif part.startswith("transport_id:"):
                    item.transport_id = part.split(":", 1)[1]

            devices.append(item)

        return devices

    def get_device_details(self, serial: str) -> DeviceDetails:
        """Retrieve complete hardware and system diagnostics for a connected device."""
        manufacturer = self.get_prop(serial, "ro.product.manufacturer") or "Android"
        model = self.get_prop(serial, "ro.product.model") or serial
        android_version = self.get_prop(serial, "ro.build.version.release") or "Unknown"
        sdk_level = self.get_prop(serial, "ro.build.version.sdk") or "Unknown"
        cpu_abi = self.get_prop(serial, "ro.product.cpu.abi") or "Unknown"

        phys_res, override_res = self.get_display_size(serial)
        density = self.get_display_density(serial)
        storage_free = self.get_storage_free(serial)
        ram_info = self.get_ram_info(serial)
        conn_type = "TCP/IP" if ":" in serial else "USB"

        return DeviceDetails(
            serial=serial,
            manufacturer=manufacturer,
            model=model,
            android_version=android_version,
            sdk_level=sdk_level,
            cpu_abi=cpu_abi,
            physical_resolution=phys_res,
            override_resolution=override_res,
            density=density,
            storage_free=storage_free,
            ram_info=ram_info,
            connection_type=conn_type,
        )

    def get_prop(self, serial: str, prop_name: str) -> str:
        """Read an Android system property."""
        res = self.run(["shell", "getprop", prop_name], serial=serial, timeout=5.0)
        return res.stdout.strip()

    def get_display_size(self, serial: str) -> Tuple[Tuple[int, int], Optional[Tuple[int, int]]]:
        """Read the physical and logical override screen resolution via 'wm size'."""
        res = self.run(["shell", "wm", "size"], serial=serial, timeout=5.0)
        output = res.stdout

        phys_match = re.search(r"Physical size:\s*(\d+)x(\d+)", output)
        if not phys_match:
            # Fallback for older formats or minimal wm output
            alt_match = re.search(r"(\d+)x(\d+)", output)
            if not alt_match:
                raise AdbError(f"Unable to parse display size from wm output:\n{output}")
            phys_res = (int(alt_match.group(1)), int(alt_match.group(2)))
        else:
            phys_res = (int(phys_match.group(1)), int(phys_match.group(2)))

        override_match = re.search(r"Override size:\s*(\d+)x(\d+)", output)
        override_res = (int(override_match.group(1)), int(override_match.group(2))) if override_match else None

        return phys_res, override_res

    def set_display_size(self, serial: str, width: int, height: int) -> None:
        """Apply a logical display resolution override using 'wm size'."""
        if not (100 <= width <= 10000 and 100 <= height <= 10000):
            raise ValueError(f"Resolution dimensions {width}x{height} outside permitted range [100, 10000].")

        res = self.run(["shell", "wm", "size", f"{width}x{height}"], serial=serial, timeout=8.0)
        if res.returncode != 0:
            raise AdbError(f"Failed to apply resolution: {res.stderr or res.stdout}")

    def reset_display_size(self, serial: str) -> None:
        """Reset the logical display resolution override back to native physical size."""
        res = self.run(["shell", "wm", "size", "reset"], serial=serial, timeout=8.0)
        if res.returncode != 0:
            raise AdbError(f"Failed to reset display resolution: {res.stderr or res.stdout}")

    def get_display_density(self, serial: str) -> Optional[int]:
        """Read the display density (DPI) via 'wm density'."""
        try:
            res = self.run(["shell", "wm", "density"], serial=serial, timeout=5.0)
            m = re.search(r"Physical density:\s*(\d+)", res.stdout)
            if not m:
                m = re.search(r"(\d+)", res.stdout)
            return int(m.group(1)) if m else None
        except Exception:
            return None

    def get_storage_free(self, serial: str) -> str:
        """Read free storage on /data partition."""
        try:
            res = self.run(["shell", "df", "-h", "/data"], serial=serial, timeout=5.0)
            lines = res.stdout.strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 4:
                    return f"{parts[3]} free / {parts[1]}"
            return "Available"
        except Exception:
            return "Unknown"

    def get_ram_info(self, serial: str) -> str:
        """Read total and available RAM from /proc/meminfo."""
        try:
            res = self.run(["shell", "cat", "/proc/meminfo"], serial=serial, timeout=5.0)
            total_kb = 0
            avail_kb = 0
            for line in res.stdout.splitlines():
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        total_kb = int(parts[1])
                elif line.startswith("MemAvailable:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        avail_kb = int(parts[1])

            if total_kb > 0:
                total_gb = total_kb / (1024 * 1024)
                avail_gb = avail_kb / (1024 * 1024)
                return f"{avail_gb:.1f} GB free / {total_gb:.1f} GB"
            return "4 GB RAM"
        except Exception:
            return "RAM stats unavailable"

    def list_packages(self, serial: str, filter_type: str = "all") -> List[str]:
        """Discover installed packages with optional -3 (user) or -s (system) filters."""
        args = ["shell", "pm", "list", "packages"]
        if filter_type == "user":
            args.append("-3")
        elif filter_type == "system":
            args.append("-s")

        res = self.run(args, serial=serial, timeout=12.0)
        packages: List[str] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkg = line.replace("package:", "").strip()
                if pkg:
                    packages.append(pkg)
        return sorted(packages)

    def get_package_version_info(self, serial: str, package_name: str) -> Tuple[str, str]:
        """Retrieve versionName and versionCode for an installed application."""
        try:
            res = self.run(["shell", "dumpsys", "package", package_name], serial=serial, timeout=8.0)
            version_name = "Unknown"
            version_code = "Unknown"

            vm = re.search(r"versionName=([^\s]+)", res.stdout)
            if vm:
                version_name = vm.group(1)

            vc = re.search(r"versionCode=(\d+)", res.stdout)
            if vc:
                version_code = vc.group(1)

            return version_name, version_code
        except Exception:
            return "Unknown", "Unknown"

    def get_pids_for_package(self, serial: str, package_name: str) -> List[int]:
        """Find running Process IDs (PIDs) associated with an application package."""
        pids: List[int] = []

        # Try pidof first (fastest on modern Android)
        try:
            res = self.run(["shell", "pidof", package_name], serial=serial, timeout=4.0)
            if res.returncode == 0 and res.stdout.strip():
                for token in res.stdout.strip().split():
                    if token.isdigit():
                        pids.append(int(token))
                if pids:
                    return sorted(list(set(pids)))
        except Exception:
            pass

        # Fallback to ps -A or ps
        try:
            res = self.run(["shell", "ps", "-A"], serial=serial, timeout=5.0)
            if res.returncode != 0 or not res.stdout.strip():
                res = self.run(["shell", "ps"], serial=serial, timeout=5.0)

            for line in res.stdout.splitlines():
                if package_name in line:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        pids.append(int(parts[1]))
        except Exception:
            pass

        return sorted(list(set(pids)))

    def clear_device_logcat(self, serial: str) -> None:
        """Clear device-level logcat buffers using 'logcat -c'."""
        res = self.run(["logcat", "-c"], serial=serial, timeout=6.0)
        if res.returncode != 0:
            raise AdbError(f"Failed to clear logcat buffer: {res.stderr or res.stdout}")

    def spawn_logcat_stream(self, serial: str) -> subprocess.Popen:
        """Spawn an asynchronous streaming logcat process using threadtime format and all buffers."""
        cmd = [self._adb_path, "-s", serial, "logcat", "-b", "all", "-v", "threadtime"]
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            close_fds=(not sys.platform.startswith("win")),
        )
