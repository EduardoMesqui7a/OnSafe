from __future__ import annotations

from datetime import datetime

from app.core.enums import DecisionState
from app.core.schemas import CameraConfig, ComplianceDecision
from app.services.camera_service import CameraService
from app.services.event_service import EventService
from app.storage.database import get_session, init_database
from app.storage.repositories import EventRepository


def test_event_service_lists_saved_events(tmp_path):
    init_database(f"sqlite:///{tmp_path / 'onsafe.db'}")
    camera = CameraService().register_camera(CameraConfig(name="Patio", host="10.0.0.20", port=554))
    decision = ComplianceDecision(
        camera_id=camera.id,
        track_id=11,
        person_label="Pessoa 1",
        state=DecisionState.CONFIRMED_NON_COMPLIANCE,
        missing_ppe=["helmet"],
        confidence_score=0.88,
        persistence_seconds=3.4,
        valid_inferences=4,
        rationale="Teste",
    )
    with get_session() as session:
        EventRepository(session).create("Patio", decision, "img.jpg", None)
        session.commit()
    events = EventService().list_recent_events()
    assert len(events) == 1
    assert events[0].person_label == "Pessoa 1"
