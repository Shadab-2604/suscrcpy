"""Install APK files from the desktop onto the connected Android device.

The install itself runs ``adb install -r`` in a worker thread so the UI stays
responsive, and adb's own output is reported back verbatim: whatever the device
answered (``Success`` or ``Failure [...]``) is what the panel shows.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from core.adb_manager import AdbManager
from core.process_manager import ProcessManager

logger = logging.getLogger("suscrcpy.apk_installer")


class ApkInstallError(RuntimeError):
    """Raised for problems detected before adb is started."""


@dataclass(frozen=True)
class InstallResult:
    """Outcome of one install attempt."""

    success: bool
    message: str
    output: str = ""


# Frequent adb failure codes, rendered as one plain sentence.
FAILURE_REASONS = {
    "INSTALL_FAILED_ALREADY_EXISTS": "An app with the same package is already installed.",
    "INSTALL_FAILED_UPDATE_INCOMPATIBLE": "Installed app was signed with a different key. Uninstall it first.",
    "INSTALL_FAILED_VERSION_DOWNGRADE": "This APK is older than the installed version.",
    "INSTALL_FAILED_INSUFFICIENT_STORAGE": "Not enough free storage on the device.",
    "INSTALL_FAILED_INVALID_APK": "The APK is corrupt or was not built correctly.",
    "INSTALL_FAILED_NO_MATCHING_ABIS": "The APK has no native code for this device's CPU.",
    "INSTALL_FAILED_OLDER_SDK": "The APK requires a newer Android version than the device has.",
    "INSTALL_FAILED_USER_RESTRICTED": "Installation is blocked on the device (allow installs over USB).",
    "INSTALL_FAILED_TEST_ONLY": "Test-only APK rejected. Build it without the testOnly flag.",
    "INSTALL_FAILED_ABORTED": "Install was aborted on the device.",
    "INSTALL_PARSE_FAILED_NO_CERTIFICATES": "The APK is not signed.",
}


def validate_apk_path(raw_path: str) -> Path:
    """Resolve and check a user-supplied APK path, raising ApkInstallError."""
    text = (raw_path or "").strip().strip('"').strip("'")
    if not text:
        raise ApkInstallError("Choose an APK file first.")

    path = Path(text).expanduser()
    if not path.is_file():
        raise ApkInstallError(f"APK not found: {path}")
    if path.suffix.lower() != ".apk":
        raise ApkInstallError(f"Not an APK file: {path.name}")

    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ApkInstallError(f"Cannot read {path.name}: {exc}") from exc
    if size == 0:
        raise ApkInstallError(f"{path.name} is empty.")
    return path


def _failure_reason(output: str, returncode: int) -> str:
    for code, explanation in FAILURE_REASONS.items():
        if code in output:
            return explanation

    for line in reversed([line.strip() for line in output.splitlines() if line.strip()]):
        lowered = line.lower()
        if lowered.startswith("adb:") or lowered.startswith("error") or "failed" in lowered:
            return line
    if returncode != 0:
        return f"adb exited with code {returncode}."
    return "The device did not report success."


def parse_install_output(returncode: int, stdout: str, stderr: str) -> InstallResult:
    """Turn adb's install output into one exact result without guessing."""
    output = "\n".join(part.strip() for part in (stdout, stderr) if part and part.strip())
    lowered = output.lower()

    if returncode == 0 and "success" in lowered and "failure" not in lowered:
        return InstallResult(True, "Installed successfully.", output)

    return InstallResult(False, _failure_reason(output, returncode), output)


class ApkInstallWorker(QThread):
    """Runs one ``adb install`` command off the UI thread."""

    progress = Signal(str)
    finished_install = Signal(object)  # InstallResult

    def __init__(
        self,
        adb_manager: AdbManager,
        serial: str,
        apk_path: Path,
        replace_existing: bool = True,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._adb = adb_manager
        self._serial = serial
        self._apk = apk_path
        self._replace = replace_existing

    def run(self) -> None:  # noqa: D102 - QThread entry point
        cmd: List[str] = [self._adb.adb_path, "-s", self._serial, "install"]
        if self._replace:
            cmd.append("-r")
        cmd.append(str(self._apk))

        self.progress.emit(f"Installing {self._apk.name} on {self._serial}…")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
            )
        except FileNotFoundError:
            self.finished_install.emit(
                InstallResult(False, f"adb executable not found at '{self._adb.adb_path}'.")
            )
            return
        except OSError as exc:
            self.finished_install.emit(InstallResult(False, f"Could not start adb: {exc}"))
            return

        ProcessManager.instance().register(proc)
        try:
            stdout, stderr = proc.communicate()
        finally:
            ProcessManager.instance().unregister(proc)

        result = parse_install_output(proc.returncode, stdout or "", stderr or "")
        logger.info(
            "APK install of %s on %s: %s", self._apk.name, self._serial, result.message
        )
        self.finished_install.emit(result)


class ApkInstaller(QObject):
    """Coordinates APK installs for the currently selected device."""

    started = Signal(str)  # APK file name
    progress = Signal(str)
    finished = Signal(object)  # InstallResult

    def __init__(self, adb_manager: AdbManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._adb = adb_manager
        self._worker: Optional[ApkInstallWorker] = None

    @property
    def is_installing(self) -> bool:
        return self._worker is not None

    def install(
        self, serial: Optional[str], raw_path: str, replace_existing: bool = True
    ) -> Path:
        """Start an install; raises ApkInstallError for invalid input."""
        if not serial:
            raise ApkInstallError("Connect and select a device first.")
        if self.is_installing:
            raise ApkInstallError("An install is already running.")

        apk_path = validate_apk_path(raw_path)

        self._worker = ApkInstallWorker(
            adb_manager=self._adb,
            serial=serial,
            apk_path=apk_path,
            replace_existing=replace_existing,
            parent=self,
        )
        self._worker.progress.connect(self.progress)
        self._worker.finished_install.connect(self._on_finished)
        self.started.emit(apk_path.name)
        self._worker.start()
        return apk_path

    def _on_finished(self, result: InstallResult) -> None:
        self._worker = None
        self.finished.emit(result)

    def shutdown(self) -> None:
        """Wait briefly for an in-flight install so adb is not killed mid-write."""
        worker = self._worker
        self._worker = None
        if worker is not None and worker.isRunning():
            worker.wait(3000)
