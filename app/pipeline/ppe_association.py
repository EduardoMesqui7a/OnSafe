from __future__ import annotations

from app.core.schemas import PPEAssociationResult, TrackState
from app.detectors.class_map import HELMET_CLASS, VEST_CLASS
from app.detectors.yolo_engine import Detection


def _intersection_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = max((ax2 - ax1) * (ay2 - ay1), 1)
    area_b = max((bx2 - bx1) * (by2 - by1), 1)
    return max(inter / area_a, inter / area_b)


def associate_ppe(track: TrackState, detections: list[Detection]) -> PPEAssociationResult:
    helmet_score = 0.0
    vest_score = 0.0
    ambiguity_flags: list[str] = []

    for detection in detections:
        overlap = _intersection_ratio(track.bbox, detection.bbox)
        if overlap <= 0:
            continue
        if detection.class_name == HELMET_CLASS:
            helmet_score = max(helmet_score, detection.confidence * overlap)
        elif detection.class_name == VEST_CLASS:
            vest_score = max(vest_score, detection.confidence * overlap)
        if overlap > 0.55:
            ambiguity_flags.append("high_overlap")

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
