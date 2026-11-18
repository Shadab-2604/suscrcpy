"""Chronological Event Timeline Manager for SUSCRCPY.

Records all testing workstation events (device connection, app launch,
resolution shifts, captures, recordings, crash detections, proxy changes)
tied to the active testing session.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("suscrcpy.event_manager")


@dataclass
class TimelineEvent:
    """Represents a single chronological event in the testing lifecycle."""
    event_id: str
    category: str  # device, app, screen, capture, recording, log, crash, proxy, note, session
    action: str    # e.g., 'connected', 'launched', 'screenshot_captured', 'crash_detected'
    description: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: Optional[str] = None
    device_serial: Optional[str] = None
    package_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventManager(QObject):
    """Coordinates recording and exporting chronological session events."""

    event_recorded = Signal(object)  # TimelineEvent
    timeline_cleared = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._events: List[TimelineEvent] = []
        self._counter = 0

    @property
    def events(self) -> List[TimelineEvent]:
        return list(self._events)

    def record_event(
        self,
        category: str,
        action: str,
        description: str,
        session_id: Optional[str] = None,
        device_serial: Optional[str] = None,
        package_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        """Record a new event and notify listeners."""
        self._counter += 1
        event_id = f"EVT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._counter:04d}"
        event = TimelineEvent(
            event_id=event_id,
            category=category,
            action=action,
            description=description,
            session_id=session_id,
            device_serial=device_serial,
            package_name=package_name,
            metadata=metadata or {},
        )
        self._events.append(event)
        logger.debug("Event recorded: [%s] %s - %s", category, action, description)
        self.event_recorded.emit(event)
        return event

    def clear(self) -> None:
        """Clear all events in the in-memory timeline."""
        self._events.clear()
        self._counter = 0
        self.timeline_cleared.emit()

    def export_to_json(self, destination_path: Path) -> Path:
        """Write timeline events to a JSON file."""
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [e.to_dict() for e in self._events]
        with open(destination_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("Exported %d timeline events to %s", len(payload), destination_path)
        return destination_path

    def load_from_json(self, source_path: Path) -> List[TimelineEvent]:
        """Load timeline events from an existing JSON file."""
        if not source_path.exists():
            return []
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded = [TimelineEvent(**item) for item in data]
            self._events = loaded
            self._counter = len(loaded)
            return self._events
        except Exception as e:
            logger.error("Failed to load timeline events from %s: %s", source_path, e)
            return []
