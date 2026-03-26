from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import CameraHealth
from app.core.schemas import CameraConfig, ComplianceDecision
from app.storage.models import Camera, CameraStatusModel, Event, Report


class CameraRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, config: CameraConfig) -> Camera:
        model = Camera(
            name=config.name,
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            protocol=config.protocol.value,
            stream_path=config.stream_path,
            enabled=config.enabled,
            required_ppe=",".join(config.required_ppe),
        )
        self.session.add(model)
        self.session.flush()
        status = CameraStatusModel(camera_id=model.id, health=CameraHealth.STOPPED.value)
        self.session.add(status)
        self.session.flush()
        return model

    def list(self) -> list[Camera]:
        return list(self.session.scalars(select(Camera).order_by(Camera.id)))

    def get(self, camera_id: int) -> Camera | None:
        return self.session.get(Camera, camera_id)


class CameraStatusRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        camera_id: int,
        health: str,
        last_frame_ts: datetime | None = None,
        capture_fps: float = 0.0,
        inference_fps: float = 0.0,
        latency_ms: float = 0.0,
        active_tracks: int = 0,
        latest_decision: str | None = None,
        status_message: str | None = None,
    ) -> CameraStatusModel:
        status = self.session.get(CameraStatusModel, camera_id)
        if status is None:
            status = CameraStatusModel(camera_id=camera_id, health=health)
            self.session.add(status)
        status.health = health
        status.last_frame_ts = last_frame_ts
        status.capture_fps = capture_fps
        status.inference_fps = inference_fps
        status.latency_ms = latency_ms
        status.active_tracks = active_tracks
        status.latest_decision = latest_decision
        status.status_message = status_message
        self.session.flush()
        return status

    def get(self, camera_id: int) -> CameraStatusModel | None:
        return self.session.get(CameraStatusModel, camera_id)


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        camera_name: str,
        decision: ComplianceDecision,
        image_path: str | None,
        video_path: str | None,
    ) -> Event:
        missing = ",".join(decision.missing_ppe)
        severity = "critical" if decision.state.value == "confirmed_non_compliance" else "warning"
        model = Event(
            camera_id=decision.camera_id,
            camera_name=camera_name,
            person_label=decision.person_label,
            decision_state=decision.state.value,
            severity=severity,
            missing_ppe=missing,
            confidence_score=decision.confidence_score,
            persistence_seconds=decision.persistence_seconds,
            rationale=decision.rationale,
            image_path=image_path,
            video_path=video_path,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def list_recent(self, limit: int = 100) -> list[Event]:
        stmt = select(Event).order_by(Event.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, report_kind: str, status: str, title: str, html_path: str | None, pdf_path: str | None) -> Report:
        model = Report(
            report_kind=report_kind,
            status=status,
            title=title,
            html_path=html_path,
            pdf_path=pdf_path,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def list_recent(self, limit: int = 100) -> list[Report]:
        stmt = select(Report).order_by(Report.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))
