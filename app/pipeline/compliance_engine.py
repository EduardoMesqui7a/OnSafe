from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from app.core.constants import DEFAULT_MISSING_PERSISTENCE_SECONDS, DEFAULT_MIN_VALID_INFERENCES, DEFAULT_TRACK_STABLE_HITS
from app.core.enums import DecisionState
from app.core.schemas import ComplianceDecision, PPEAssociationResult, TrackState


@dataclass
class _TemporalState:
    first_non_compliant_at: datetime | None = None
    valid_inferences: int = 0
    ambiguity_flags: set[str] = field(default_factory=set)
    latest_present: dict[str, bool] = field(default_factory=dict)


class ComplianceEngine:
    def __init__(
        self,
        min_track_hits: int = DEFAULT_TRACK_STABLE_HITS,
        min_valid_inferences: int = DEFAULT_MIN_VALID_INFERENCES,
        min_persistence_seconds: float = DEFAULT_MISSING_PERSISTENCE_SECONDS,
    ) -> None:
        self.min_track_hits = min_track_hits
        self.min_valid_inferences = min_valid_inferences
        self.min_persistence_seconds = min_persistence_seconds
        self._state: dict[tuple[int, int], _TemporalState] = defaultdict(_TemporalState)

    def evaluate(
        self,
        camera_id: int,
        track: TrackState,
        association: PPEAssociationResult,
        required_ppe: list[str],
        timestamp: datetime,
    ) -> ComplianceDecision:
        state = self._state[(camera_id, track.track_id)]
        missing: list[str] = []
        if "helmet" in required_ppe and not association.helmet_present:
            missing.append("helmet")
        if "vest" in required_ppe and not association.vest_present:
            missing.append("vest")

        if track.stability_hits < self.min_track_hits:
            return ComplianceDecision(
                camera_id=camera_id,
                track_id=track.track_id,
                person_label=track.label,
                state=DecisionState.DISCARDED_DUE_TO_UNCERTAINTY,
                confidence_score=0.0,
                persistence_seconds=0.0,
                valid_inferences=state.valid_inferences,
                ambiguity_flags=[],
                rationale="Track ainda instável; classificação conservadora aplicada.",
            )

        state.valid_inferences += 1
        state.ambiguity_flags.update(association.ambiguity_flags)

        if not missing:
            state.first_non_compliant_at = None
            state.latest_present = {"helmet": association.helmet_present, "vest": association.vest_present}
            return ComplianceDecision(
                camera_id=camera_id,
                track_id=track.track_id,
                person_label=track.label,
                state=DecisionState.COMPLIANT,
                confidence_score=max(association.helmet_confidence, association.vest_confidence),
                persistence_seconds=0.0,
                valid_inferences=state.valid_inferences,
                ambiguity_flags=list(state.ambiguity_flags),
                rationale="Pessoa com EPIs obrigatórios presentes dentro dos limiares configurados.",
            )

        if state.first_non_compliant_at is None:
            state.first_non_compliant_at = timestamp
        persistence = (timestamp - state.first_non_compliant_at).total_seconds()
        confidence = 0.0
        if "helmet" in missing:
            confidence += max(0.0, 1.0 - association.helmet_confidence)
        if "vest" in missing:
            confidence += max(0.0, 1.0 - association.vest_confidence)
        confidence = round(confidence / max(len(missing), 1), 3)

        if state.valid_inferences < self.min_valid_inferences or persistence < self.min_persistence_seconds:
            return ComplianceDecision(
                camera_id=camera_id,
                track_id=track.track_id,
                person_label=track.label,
                state=DecisionState.SUSPECTED_NON_COMPLIANCE,
                missing_ppe=missing,
                confidence_score=confidence,
                persistence_seconds=persistence,
                valid_inferences=state.valid_inferences,
                ambiguity_flags=list(state.ambiguity_flags),
                rationale="Não conformidade suspeita, mas ainda sem persistência ou amostragem suficiente.",
            )

        if state.ambiguity_flags:
            return ComplianceDecision(
                camera_id=camera_id,
                track_id=track.track_id,
                person_label=track.label,
                state=DecisionState.DISCARDED_DUE_TO_UNCERTAINTY,
                missing_ppe=missing,
                confidence_score=confidence,
                persistence_seconds=persistence,
                valid_inferences=state.valid_inferences,
                ambiguity_flags=list(state.ambiguity_flags),
                rationale="Ambiguidade relevante encontrada na associação pessoa/EPI; evento marcado como duvidoso.",
            )

        return ComplianceDecision(
            camera_id=camera_id,
            track_id=track.track_id,
            person_label=track.label,
            state=DecisionState.CONFIRMED_NON_COMPLIANCE,
            missing_ppe=missing,
            confidence_score=confidence,
            persistence_seconds=persistence,
            valid_inferences=state.valid_inferences,
            ambiguity_flags=list(state.ambiguity_flags),
            rationale=(
                f"Não conformidade confirmada após {persistence:.1f}s de persistência, "
                f"{state.valid_inferences} inferências válidas e track estável."
            ),
        )
