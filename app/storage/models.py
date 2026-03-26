from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class Camera(Base, TimestampMixin):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String(120))
    password: Mapped[str | None] = mapped_column(String(255))
    protocol: Mapped[str] = mapped_column(String(16), nullable=False)
    stream_path: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    required_ppe: Mapped[str] = mapped_column(String(120), default="helmet,vest", nullable=False)

    events: Mapped[list["Event"]] = relationship(back_populates="camera")


class CameraStatusModel(Base):
    __tablename__ = "camera_status"

    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), primary_key=True)
    health: Mapped[str] = mapped_column(String(32), nullable=False)
    last_frame_ts: Mapped[datetime | None] = mapped_column(DateTime)
    capture_fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    inference_fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    active_tracks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_decision: Mapped[str | None] = mapped_column(String(64))


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), nullable=False)
    camera_name: Mapped[str] = mapped_column(String(120), nullable=False)
    person_label: Mapped[str] = mapped_column(String(120), nullable=False)
    decision_state: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    missing_ppe: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    persistence_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(255))
    video_path: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    camera: Mapped["Camera"] = relationship(back_populates="events")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    html_path: Mapped[str | None] = mapped_column(String(255))
    pdf_path: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
