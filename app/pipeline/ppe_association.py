from __future__ import annotations

from app.core.schemas import PPEAssociationResult, TrackState
from app.detectors.class_map import HELMET_CLASS, VEST_CLASS
from app.detectors.yolo_engine import Detection


def _item_center(box: tuple[int, int, int, int]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return 0.5 * (x1 + x2), 0.5 * (y1 + y2)


def _inside_region(cx: float, cy: float, region: tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = region
    return x1 <= cx <= x2 and y1 <= cy <= y2


def _head_region(person_box: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    px1, py1, px2, py2 = person_box
    pw = px2 - px1
    ph = py2 - py1
    return (
        px1 + 0.10 * pw,
        py1,
        px2 - 0.10 * pw,
        py1 + 0.32 * ph,
    )


def _torso_region(person_box: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    px1, py1, px2, py2 = person_box
    pw = px2 - px1
    ph = py2 - py1
    return (
        px1 + 0.12 * pw,
        py1 + 0.28 * ph,
        px2 - 0.12 * pw,
        py1 + 0.80 * ph,
    )


def associate_ppe(track: TrackState, detections: list[Detection]) -> PPEAssociationResult:
    helmet_score = 0.0
    vest_score = 0.0
    ambiguity_flags: list[str] = []
    head_region = _head_region(track.bbox)
    torso_region = _torso_region(track.bbox)

    for detection in detections:
        center_x, center_y = _item_center(detection.bbox)
        if detection.class_name == HELMET_CLASS:
            if _inside_region(center_x, center_y, head_region):
                helmet_score = max(helmet_score, detection.confidence)
        elif detection.class_name == VEST_CLASS:
            if _inside_region(center_x, center_y, torso_region):
                vest_score = max(vest_score, detection.confidence)
        else:
            ambiguity_flags.append("unmapped_detection")

    return PPEAssociationResult(
        track_id=track.track_id,
        display_person_id=track.display_person_id,
        helmet_present=helmet_score >= 0.45,
        vest_present=vest_score >= 0.45,
        helmet_confidence=helmet_score,
        vest_confidence=vest_score,
        ambiguity_flags=sorted(set(ambiguity_flags)),
        overlap_score=max(helmet_score, vest_score),
    )
