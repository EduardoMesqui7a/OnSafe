from __future__ import annotations

from datetime import datetime, timedelta

from app.core.enums import DecisionState
from app.core.schemas import PPEAssociationResult, TrackState
from app.pipeline.compliance_engine import ComplianceEngine


def test_compliance_engine_confirms_only_after_persistence_and_track_stability():
    engine = ComplianceEngine(min_track_hits=3, min_valid_inferences=2, min_persistence_seconds=1.0)
    track = TrackState(
        camera_id=1,
        track_id=7,
        display_person_id=1,
        label="Pessoa 1",
        bbox=(0, 0, 50, 100),
        stability_hits=3,
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
    )
    association = PPEAssociationResult(
        track_id=7,
        display_person_id=1,
        helmet_present=False,
        vest_present=False,
        helmet_confidence=0.0,
        vest_confidence=0.0,
    )
    first = engine.evaluate(1, track, association, ["helmet", "vest"], datetime.utcnow())
    second = engine.evaluate(1, track, association, ["helmet", "vest"], datetime.utcnow() + timedelta(seconds=1.2))
    assert first.state == DecisionState.SUSPECTED_NON_COMPLIANCE
    assert second.state == DecisionState.CONFIRMED_NON_COMPLIANCE
