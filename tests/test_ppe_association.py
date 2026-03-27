from __future__ import annotations

from datetime import datetime

from app.core.schemas import TrackState
from app.detectors.class_map import HELMET_CLASS, PERSON_CLASS, VEST_CLASS, normalize_class_name
from app.detectors.yolo_engine import Detection
from app.pipeline.ppe_association import associate_ppe


def test_associate_ppe_marks_present_when_overlap_is_sufficient():
    track = TrackState(
        camera_id=1,
        track_id=99,
        display_person_id=1,
        label="Pessoa 1",
        bbox=(0, 0, 100, 200),
        stability_hits=3,
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
    )
    detections = [
        Detection(class_name=HELMET_CLASS, confidence=0.95, bbox=(10, 0, 90, 50)),
        Detection(class_name=VEST_CLASS, confidence=0.90, bbox=(10, 60, 90, 180)),
    ]
    association = associate_ppe(track, detections)
    assert association.helmet_present is True
    assert association.vest_present is True


def test_class_aliases_are_normalized_to_supported_names():
    assert normalize_class_name("pessoa") == "person"
    assert normalize_class_name("capacete") == "helmet"
    assert normalize_class_name("colete") == "vest"
    assert normalize_class_name("hardhat") == "helmet"
    assert normalize_class_name("no helmet") is None


def test_associate_ppe_does_not_mark_person_detection_as_ambiguity():
    track = TrackState(
        camera_id=1,
        track_id=100,
        display_person_id=1,
        label="Pessoa 1",
        bbox=(0, 0, 100, 200),
        stability_hits=3,
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
    )
    detections = [
        Detection(class_name=PERSON_CLASS, confidence=0.92, bbox=(0, 0, 100, 200), track_id=100),
    ]
    association = associate_ppe(track, detections)
    assert association.ambiguity_flags == []
