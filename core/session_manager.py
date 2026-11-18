"""Testing Session Manager for SUSCRCPY Workstation.

Coordinates structured testing sessions, binds connected device specifications,
target application metadata, test types, and tester notes into a single cohesive
testing context. Detects and recovers interrupted sessions after sudden crashes.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from core.evidence_manager import EvidenceManager

logger = logging.getLogger("suscrcpy.session_manager")

TEST_TYPES = [
    "Functional Testing",
    "Frontend/UI Testing",
    "Backend/API Testing",
    "Regression Testing",
    "Compatibility Testing",
    "Performance Testing",
    "Security Testing",
    "Smoke Testing",
    "Exploratory Testing",
    "Custom",
]


class SessionStatus(str, Enum):
    CREATED = "Created"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    INTERRUPTED = "Interrupted"


@dataclass
class SessionMetadata:
    """Full metadata defining an active or historical testing session."""
    session_id: str
    session_name: str
    project_name: str = "DefaultProject"
    test_type: str = "Functional Testing"
    tester_name: str = ""
    tester_notes: str = ""
    status: str = SessionStatus.CREATED.value
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: Optional[str] = None
    
    # Device details
    device_serial: str = ""
    device_model: str = ""
    device_manufacturer: str = ""
    android_version: str = ""
    sdk_version: str = ""
    screen_dimensions: Tuple[int, int] = (0, 0)
    display_density: Optional[int] = None
    
    # Target Application details
    target_app_name: str = ""
    target_package: str = ""
    app_version: str = ""
    app_version_code: str = ""

    # Statistics
    total_logs: int = 0
    total_errors: int = 0
    total_crashes: int = 0
    total_screenshots: int = 0
    total_recordings: int = 0
    total_observations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SessionManager(QObject):
    """Manages active testing session state, atomic persistence, and recovery."""

    session_started = Signal(object)       # SessionMetadata
    session_state_changed = Signal(object) # SessionMetadata
    session_ended = Signal(object)         # SessionMetadata
    interrupted_session_found = Signal(object) # SessionMetadata

    def __init__(self, evidence_manager: EvidenceManager, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.evidence = evidence_manager
        self._current_session: Optional[SessionMetadata] = None

    @property
    def active_session(self) -> Optional[SessionMetadata]:
        return self._current_session

    @property
    def is_active(self) -> bool:
        return self._current_session is not None and self._current_session.status in (
            SessionStatus.RUNNING.value,
            SessionStatus.PAUSED.value,
        )

    def generate_session_id(self) -> str:
        """Generate unique session ID formatted as SUS-YYYYMMDD-XXXX."""
        date_str = datetime.now().strftime("%Y%m%d")
        # Find next sequence number
        seq = 1
        base_dir = self.evidence.base_dir
        if base_dir.exists():
            for root, dirs, _ in os.walk(base_dir):
                for d in dirs:
                    if d.startswith(f"SUS-{date_str}-"):
                        try:
                            num = int(d.split("-")[-1])
                            seq = max(seq, num + 1)
                        except ValueError:
                            pass
        return f"SUS-{date_str}-{seq:04d}"

    def create_session(
        self,
        session_name: str,
        project_name: str,
        test_type: str = "Functional Testing",
        tester_name: str = "",
        tester_notes: str = "",
        device_serial: str = "",
        device_model: str = "",
        device_manufacturer: str = "",
        android_version: str = "",
        sdk_version: str = "",
        screen_dimensions: Tuple[int, int] = (0, 0),
        display_density: Optional[int] = None,
        target_app_name: str = "",
        target_package: str = "",
        app_version: str = "",
        app_version_code: str = "",
    ) -> SessionMetadata:
        """Create a new testing session and initialize its evidence folder."""
        session_id = self.generate_session_id()
        self.evidence.init_session_directory(project_name, session_id)

        meta = SessionMetadata(
            session_id=session_id,
            session_name=session_name.strip() or f"Session {session_id}",
            project_name=project_name.strip() or "DefaultProject",
            test_type=test_type if test_type in TEST_TYPES else "Functional Testing",
            tester_name=tester_name.strip(),
            tester_notes=tester_notes.strip(),
            status=SessionStatus.CREATED.value,
            start_time=datetime.now().isoformat(),
            device_serial=device_serial,
            device_model=device_model,
            device_manufacturer=device_manufacturer,
            android_version=android_version,
            sdk_version=sdk_version,
            screen_dimensions=screen_dimensions,
            display_density=display_density,
            target_app_name=target_app_name,
            target_package=target_package,
            app_version=app_version,
            app_version_code=app_version_code,
        )
        self._current_session = meta
        self.save_session()
        logger.info("Created session %s (%s)", meta.session_id, meta.session_name)
        return meta

    def start_session(self) -> None:
        """Start or resume running the active session."""
        if not self._current_session:
            return
        self._current_session.status = SessionStatus.RUNNING.value
        self.save_session()
        logger.info("Session %s transitioned to RUNNING", self._current_session.session_id)
        self.session_started.emit(self._current_session)
        self.session_state_changed.emit(self._current_session)

    def pause_session(self) -> None:
        """Temporarily pause active testing session."""
        if not self._current_session or self._current_session.status != SessionStatus.RUNNING.value:
            return
        self._current_session.status = SessionStatus.PAUSED.value
        self.save_session()
        logger.info("Session %s PAUSED", self._current_session.session_id)
        self.session_state_changed.emit(self._current_session)

    def resume_session(self) -> None:
        """Resume paused testing session."""
        if not self._current_session or self._current_session.status != SessionStatus.PAUSED.value:
            return
        self._current_session.status = SessionStatus.RUNNING.value
        self.save_session()
        logger.info("Session %s RESUMED", self._current_session.session_id)
        self.session_state_changed.emit(self._current_session)

    def end_session(self) -> Optional[SessionMetadata]:
        """Conclude active session and mark it COMPLETED."""
        if not self._current_session:
            return None
        self._current_session.status = SessionStatus.COMPLETED.value
        self._current_session.end_time = datetime.now().isoformat()
        self.save_session()
        logger.info("Session %s COMPLETED", self._current_session.session_id)
        ended = self._current_session
        self.session_ended.emit(ended)
        self.session_state_changed.emit(ended)
        return ended

    def save_session(self) -> Optional[Path]:
        """Atomically persist current session metadata to session.json."""
        if not self._current_session:
            return None
        session_dir = self.evidence.current_session_dir
        if not session_dir:
            return None

        filepath = session_dir / "session.json"
        tmp_filepath = session_dir / "session.json.tmp"
        payload = self._current_session.to_dict()

        try:
            with open(tmp_filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            tmp_filepath.replace(filepath)
            return filepath
        except Exception as e:
            logger.error("Failed to save session metadata: %s", e)
            return None

    def scan_for_interrupted_sessions(self) -> List[SessionMetadata]:
        """Scan evidence directory for sessions that were left RUNNING or PAUSED."""
        interrupted: List[SessionMetadata] = []
        base_dir = self.evidence.base_dir
        if not base_dir.exists():
            return []

        for root, _, files in os.walk(base_dir):
            if "session.json" in files:
                json_path = Path(root) / "session.json"
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    status = data.get("status")
                    if status in (SessionStatus.RUNNING.value, SessionStatus.PAUSED.value):
                        data["status"] = SessionStatus.INTERRUPTED.value
                        meta = SessionMetadata(**data)
                        # Mark as interrupted on disk
                        with open(json_path, "w", encoding="utf-8") as fw:
                            json.dump(meta.to_dict(), fw, indent=2, ensure_ascii=False)
                        interrupted.append(meta)
                        self.interrupted_session_found.emit(meta)
                except Exception as e:
                    logger.debug("Could not parse session at %s: %s", json_path, e)
        return interrupted

    def recover_session(self, meta: SessionMetadata) -> None:
        """Set an interrupted or historical session as the current session."""
        self.evidence.init_session_directory(meta.project_name, meta.session_id)
        self._current_session = meta
        self._current_session.status = SessionStatus.PAUSED.value
        self.save_session()
        self.session_state_changed.emit(self._current_session)
