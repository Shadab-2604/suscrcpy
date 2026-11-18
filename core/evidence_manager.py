"""Evidence Management & File Integrity System for SUSCRCPY.

Maintains structured, session-specific evidence directories, manages raw and
annotated screenshots, video recordings, log dumps, notes, and cryptographic
SHA-256 manifests.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("suscrcpy.evidence_manager")

LOW_DISK_SPACE_WARNING_MB = 500


@dataclass
class EvidenceItem:
    """Represents a single evidence asset within a session."""
    relative_path: str
    category: str  # screenshot, recording, log, note, report, event
    filename: str
    size_bytes: int
    sha256: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceManager(QObject):
    """Manages session directories, evidence files, hashes, and disk space health."""

    evidence_item_added = Signal(object)  # EvidenceItem
    manifest_generated = Signal(str)      # manifest path
    low_disk_space_warning = Signal(int)  # free MBs remaining

    def __init__(self, base_evidence_dir: Optional[Path] = None, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.base_dir = base_evidence_dir or (Path.home() / "SUSCRCPY-Evidence")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._current_session_dir: Optional[Path] = None

    @property
    def current_session_dir(self) -> Optional[Path]:
        return self._current_session_dir

    def init_session_directory(self, project_name: str, session_id: str) -> Path:
        """Create structured hierarchy for a testing session."""
        clean_project = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in project_name.strip()) or "DefaultProject"
        session_dir = self.base_dir / clean_project / session_id
        
        # Subdirectories
        (session_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        (session_dir / "recordings").mkdir(parents=True, exist_ok=True)
        (session_dir / "logs").mkdir(parents=True, exist_ok=True)
        (session_dir / "notes").mkdir(parents=True, exist_ok=True)
        (session_dir / "events").mkdir(parents=True, exist_ok=True)
        (session_dir / "reports").mkdir(parents=True, exist_ok=True)
        (session_dir / "exports").mkdir(parents=True, exist_ok=True)

        self._current_session_dir = session_dir
        logger.info("Initialized session evidence directory: %s", session_dir)
        self.check_disk_space()
        return session_dir

    def get_subdirectory(self, name: str) -> Path:
        """Get absolute path to a specific session subfolder."""
        if not self._current_session_dir:
            fallback = self.base_dir / "temp" / name
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
        sub = self._current_session_dir / name
        sub.mkdir(parents=True, exist_ok=True)
        return sub

    @staticmethod
    def calculate_file_sha256(filepath: Path) -> str:
        """Calculate SHA-256 cryptographic digest of a file in chunks."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def generate_manifest(self) -> Tuple[Path, List[EvidenceItem]]:
        """Scan session directory, compute SHA-256 for all assets, and write evidence_manifest.json."""
        if not self._current_session_dir or not self._current_session_dir.exists():
            raise RuntimeError("No active session directory initialized")

        manifest_items: List[EvidenceItem] = []
        for root, _, files in os.walk(self._current_session_dir):
            for filename in files:
                filepath = Path(root) / filename
                if filepath.name == "evidence_manifest.json":
                    continue
                try:
                    rel = str(filepath.relative_to(self._current_session_dir))
                    category = rel.split(os.sep)[0] if os.sep in rel else "root"
                    size = filepath.stat().st_size
                    created_at = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
                    sha256 = self.calculate_file_sha256(filepath)
                    item = EvidenceItem(
                        relative_path=rel,
                        category=category,
                        filename=filename,
                        size_bytes=size,
                        sha256=sha256,
                        created_at=created_at,
                    )
                    manifest_items.append(item)
                except Exception as e:
                    logger.warning("Failed to hash file %s: %s", filepath, e)

        exports_dir = self.get_subdirectory("exports")
        manifest_path = exports_dir / "evidence_manifest.json"
        
        manifest_data = {
            "generated_at": datetime.now().isoformat(),
            "session_directory": str(self._current_session_dir),
            "total_files": len(manifest_items),
            "total_bytes": sum(item.size_bytes for item in manifest_items),
            "files": [item.to_dict() for item in manifest_items],
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)

        logger.info("Generated evidence manifest with %d items at %s", len(manifest_items), manifest_path)
        self.manifest_generated.emit(str(manifest_path))
        return manifest_path, manifest_items

    def check_disk_space(self) -> int:
        """Check available disk space in MB and emit alert if critically low."""
        try:
            target = self._current_session_dir or self.base_dir
            usage = shutil.disk_usage(target)
            free_mb = int(usage.free / (1024 * 1024))
            if free_mb < LOW_DISK_SPACE_WARNING_MB:
                logger.warning("Low disk space warning: %d MB remaining on evidence storage partition", free_mb)
                self.low_disk_space_warning.emit(free_mb)
            return free_mb
        except Exception as e:
            logger.warning("Could not check disk usage: %s", e)
            return 999999
