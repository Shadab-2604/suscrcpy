"""Log export utility for SUSCRCPY.

Formats and exports captured Android log streams to structured text or log files
with comprehensive diagnostic metadata and security warnings.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import List, Optional

from core.adb_manager import DeviceDetails
from core.log_manager import LogEntry

logger = logging.getLogger("suscrcpy.log_exporter")


class LogExporter:
    """Exports log entries with full session metadata to .log or .txt files."""

    @staticmethod
    def generate_default_filename(
        device_model: str,
        mode_or_app: str,
        extension: str = "log",
    ) -> str:
        """Generate a clean timestamped filename."""
        clean_model = re.sub(r"[^\w\-]", "_", device_model).strip("_") or "device"
        clean_target = re.sub(r"[^\w\-]", "_", mode_or_app).strip("_") or "full"
        ts = time.strftime("%Y%m%d_%H%M%S")
        return f"suscrcpy_{clean_model}_{clean_target}_{ts}.{extension}"

    @staticmethod
    def export_to_file(
        filepath: str,
        logs: List[LogEntry],
        details: Optional[DeviceDetails],
        mode: str,
        start_time: Optional[str] = None,
        error_count: int = 0,
        warning_count: int = 0,
        crash_count: int = 0,
    ) -> int:
        """Write all captured logs along with diagnostic header metadata.

        Returns total number of lines written.
        """
        end_time = time.strftime("%Y-%m-%d %H:%M:%S")
        start = start_time or end_time

        dev_model = details.model if details else "Unknown Model"
        dev_serial = details.serial if details else "Unknown Serial"
        android_ver = f"{details.android_version} (SDK {details.sdk_level})" if details else "Unknown"

        header_lines = [
            "=" * 80,
            "SUSCRCPY 2.0.0 — Android Device Log Export",
            "=" * 80,
            f"Device Model     : {dev_model}",
            f"Device Serial    : {dev_serial}",
            f"Android OS       : {android_ver}",
            f"Capture Mode     : {mode}",
            f"Capture Started  : {start}",
            f"Capture Ended    : {end_time}",
            f"Total Entries    : {len(logs)}",
            f"Errors Detected  : {error_count}",
            f"Warnings         : {warning_count}",
            f"Crashes/ANRs     : {crash_count}",
            "=" * 80,
            "SECURITY NOTICE:",
            "Device logs may contain sensitive information, tokens, authentication headers,",
            "PII, or internal endpoints. Handle and store this export securely.",
            "=" * 80,
            "",
        ]

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(header_lines) + "\n")
                for entry in logs:
                    f.write(f"{entry.raw}\n")

            logger.info("Successfully exported %d logs to %s", len(logs), filepath)
            return len(logs)
        except Exception as e:
            logger.error("Failed to export logs to %s: %s", filepath, e)
            raise
