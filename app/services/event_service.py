from __future__ import annotations

from app.core.enums import DecisionState, EventSeverity
from app.core.schemas import EventView
from app.storage.database import get_session
from app.storage.repositories import EventRepository


class EventService:
    def list_recent_events(self, limit: int = 100) -> list[EventView]:
        with get_session() as session:
            items = EventRepository(session).list_recent(limit=limit)
            return [
                EventView(
                    id=item.id,
                    camera_name=item.camera_name,
                    person_label=item.person_label,
                    decision_state=DecisionState(item.decision_state),
                    severity=EventSeverity(item.severity),
                    missing_ppe=item.missing_ppe.split(",") if item.missing_ppe else [],
                    confidence_score=item.confidence_score,
                    persistence_seconds=item.persistence_seconds,
                    rationale=item.rationale,
                    image_path=item.image_path,
                    video_path=item.video_path,
                    created_at=item.created_at,
                )
                for item in items
            ]
