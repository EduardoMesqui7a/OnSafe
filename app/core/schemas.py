from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import CameraHealth, DecisionState, EventSeverity, Protocol, ReportKind, ReportStatus


class CameraConfig(BaseModel):
    name: str
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    protocol: Protocol = Protocol.RTSP
    stream_path: str = ""
    enabled: bool = True
    required_ppe: list[str] = Field(default_factory=lambda: ["helmet", "vest"])

    @field_validator("required_ppe", mode="before")
    @classmethod
    def _normalize_required_ppe(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def build_stream_url(self) -> str:
        if self.uses_browser_input():
            return "browser://camera"
        if self.uses_local_device():
            return "local://0"
        auth = ""
        if self.username:
            password = self.password or ""
            auth = f"{self.username}:{password}@"
        base = f"{self.protocol.value}://{auth}{self.host}:{self.port}"
        path = self.stream_path.strip("/")
        return f"{base}/{path}" if path else base

    def uses_local_device(self) -> bool:
        return str(self.host).strip() == "0"

    def uses_browser_input(self) -> bool:
        return str(self.host).strip().lower() in {"__browser__", "browser"}

    def get_capture_source(self) -> str | int:
        if self.uses_browser_input():
            raise ValueError("Browser camera input is handled by Streamlit UI, not OpenCV capture.")
        return 0 if self.uses_local_device() else self.build_stream_url()


class CameraRecord(CameraConfig):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class CameraTestResult(BaseModel):
    success: bool
    status: CameraHealth
    message: str
    latency_ms: float | None = None
    stream_url: str | None = None


class OperationResult(BaseModel):
    success: bool
    message: str


class CameraStatus(BaseModel):
    camera_id: int
    health: CameraHealth
    last_frame_ts: datetime | None = None
    capture_fps: float = 0.0
    inference_fps: float = 0.0
    latency_ms: float = 0.0
    active_tracks: int = 0
    latest_decision: DecisionState | None = None
    status_message: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class FramePacket(BaseModel):
    camera_id: int
    frame: Any
    timestamp: datetime
    annotated: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class TrackState(BaseModel):
    camera_id: int
    track_id: int
    display_person_id: int
    label: str
    bbox: tuple[int, int, int, int]
    stability_hits: int = 0
    first_seen: datetime
    last_seen: datetime


class TrackView(BaseModel):
    camera_id: int
    label: str
    track_id: int
    bbox: tuple[int, int, int, int]
    stability_hits: int
    last_seen: datetime


class PPEAssociationResult(BaseModel):
    track_id: int
    display_person_id: int
    helmet_present: bool
    vest_present: bool
    helmet_confidence: float = 0.0
    vest_confidence: float = 0.0
    ambiguity_flags: list[str] = Field(default_factory=list)
    overlap_score: float = 0.0


class ComplianceDecision(BaseModel):
    camera_id: int
    track_id: int
    person_label: str
    track_bbox: tuple[int, int, int, int] | None = None
    state: DecisionState
    missing_ppe: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    persistence_seconds: float = 0.0
    valid_inferences: int = 0
    ambiguity_flags: list[str] = Field(default_factory=list)
    rationale: str


class EventRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    camera_id: int
    camera_name: str
    person_label: str
    decision_state: DecisionState
    severity: EventSeverity
    missing_ppe: list[str]
    confidence_score: float
    persistence_seconds: float
    rationale: str
    image_path: str | None = None
    video_path: str | None = None
    created_at: datetime


class EventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    camera_name: str
    person_label: str
    decision_state: DecisionState
    severity: EventSeverity
    missing_ppe: list[str]
    confidence_score: float
    persistence_seconds: float
    rationale: str
    image_path: str | None
    video_path: str | None
    created_at: datetime


class ReportRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    report_kind: ReportKind
    status: ReportStatus
    title: str
    html_path: str | None
    pdf_path: str | None
    created_at: datetime
