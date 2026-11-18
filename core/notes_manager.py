"""Test Observations and Bug Notes Manager for SUSCRCPY.

Allows testers to record, categorize, edit, and link observations to screenshots,
logcat snippets, and active testing sessions.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("suscrcpy.notes_manager")

SEVERITIES = ["Critical", "High", "Medium", "Low", "Informational"]
CATEGORIES = [
    "UI/UX",
    "Functional",
    "API/Backend",
    "Performance",
    "Compatibility",
    "Security",
    "Crash",
    "Network",
]


@dataclass
class TestObservation:
    """Represents a structured defect or observation recorded during testing."""
    obs_id: str
    title: str
    description: str
    severity: str = "Medium"
    category: str = "Functional"
    expected_result: str = ""
    actual_result: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: Optional[str] = None
    package_name: Optional[str] = None
    screenshot_path: Optional[str] = None
    log_excerpts: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NotesManager(QObject):
    """Manages creation, editing, deletion and export of test observations."""

    observation_added = Signal(object)    # TestObservation
    observation_updated = Signal(object)  # TestObservation
    observation_deleted = Signal(str)     # obs_id
    notes_cleared = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._observations: List[TestObservation] = []
        self._counter = 0

    @property
    def observations(self) -> List[TestObservation]:
        return list(self._observations)

    def add_observation(
        self,
        title: str,
        description: str,
        severity: str = "Medium",
        category: str = "Functional",
        expected_result: str = "",
        actual_result: str = "",
        session_id: Optional[str] = None,
        package_name: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        log_excerpts: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> TestObservation:
        """Create and register a new test observation."""
        self._counter += 1
        obs_id = f"OBS-{datetime.now().strftime('%Y%m%d')}-{self._counter:03d}"
        if severity not in SEVERITIES:
            severity = "Medium"
        if category not in CATEGORIES:
            category = "Functional"

        obs = TestObservation(
            obs_id=obs_id,
            title=title.strip(),
            description=description.strip(),
            severity=severity,
            category=category,
            expected_result=expected_result.strip(),
            actual_result=actual_result.strip(),
            session_id=session_id,
            package_name=package_name,
            screenshot_path=screenshot_path,
            log_excerpts=log_excerpts or [],
            tags=tags or [],
        )
        self._observations.append(obs)
        logger.info("Recorded observation: [%s] %s (%s)", obs.severity, obs.title, obs.obs_id)
        self.observation_added.emit(obs)
        return obs

    def update_observation(
        self,
        obs_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        expected_result: Optional[str] = None,
        actual_result: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        log_excerpts: Optional[List[str]] = None,
    ) -> Optional[TestObservation]:
        """Update fields of an existing observation."""
        for obs in self._observations:
            if obs.obs_id == obs_id:
                if title is not None:
                    obs.title = title.strip()
                if description is not None:
                    obs.description = description.strip()
                if severity is not None and severity in SEVERITIES:
                    obs.severity = severity
                if category is not None and category in CATEGORIES:
                    obs.category = category
                if expected_result is not None:
                    obs.expected_result = expected_result.strip()
                if actual_result is not None:
                    obs.actual_result = actual_result.strip()
                if screenshot_path is not None:
                    obs.screenshot_path = screenshot_path
                if log_excerpts is not None:
                    obs.log_excerpts = log_excerpts
                self.observation_updated.emit(obs)
                return obs
        return None

    def delete_observation(self, obs_id: str) -> bool:
        """Remove an observation by ID."""
        for i, obs in enumerate(self._observations):
            if obs.obs_id == obs_id:
                del self._observations[i]
                logger.info("Deleted observation %s", obs_id)
                self.observation_deleted.emit(obs_id)
                return True
        return False

    def clear(self) -> None:
        """Clear all in-memory observations."""
        self._observations.clear()
        self._counter = 0
        self.notes_cleared.emit()

    def export_to_json(self, destination_path: Path) -> Path:
        """Serialize all observations to a JSON file."""
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [obs.to_dict() for obs in self._observations]
        with open(destination_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("Exported %d observations to %s", len(payload), destination_path)
        return destination_path

    def load_from_json(self, source_path: Path) -> List[TestObservation]:
        """Load observations from JSON file."""
        if not source_path.exists():
            return []
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = [TestObservation(**item) for item in data]
            self._observations = loaded
            self._counter = len(loaded)
            return self._observations
        except Exception as e:
            logger.error("Failed to load observations from %s: %s", source_path, e)
            return []
