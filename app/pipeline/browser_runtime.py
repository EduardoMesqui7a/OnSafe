from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.core.enums import CameraHealth, DecisionState, EventSeverity
from app.core.schemas import CameraConfig, CameraStatus, EventView
from app.detectors.class_map import PERSON_CLASS
from app.detectors.yolo_engine import YoloEngine
from app.pipeline.compliance_engine import ComplianceEngine
from app.pipeline.evidence_writer import EvidenceJob, EvidenceWriter
from app.pipeline.frame_store import FrameStore
from app.pipeline.inference_scheduler import InferenceScheduler
from app.pipeline.ppe_association import associate_ppe
from app.pipeline.report_worker import ReportJob, ReportWorker
from app.pipeline.tracker_manager import TrackerManager
from app.storage.database import get_session
from app.storage.repositories import CameraStatusRepository, EventRepository

logger = logging.getLogger(__name__)


class BrowserCameraRuntime:
    def __init__(
        self,
        camera_id: int,
        config: CameraConfig,
        settings: Settings,
        evidence_writer: EvidenceWriter,
        report_worker: ReportWorker,
        model_path: str,
    ) -> None:
        self.camera_id = camera_id
        self.config = config
        self.settings = settings
        self.evidence_writer = evidence_writer
        self.report_worker = report_worker
        self.frame_store = FrameStore(settings.ring_buffer_seconds, settings.preview_fps)
        self.tracker = TrackerManager()
        self.compliance_engine = ComplianceEngine()
        self.scheduler = InferenceScheduler(settings.inference_fps)
        self.yolo_engine = YoloEngine(model_path, settings.inference_image_size)
        self.capture_fps = 0.0
        self.inference_fps = 0.0
        self.latest_decision: DecisionState | None = None
        self.status_message: str | None = None
        self.last_frame_ts: datetime | None = None
        self.health = CameraHealth.STARTING
        self._capture_count = 0
        self._infer_count = 0
        self._capture_window_started = time.monotonic()
        self._infer_window_started = time.monotonic()
        self._event_history: dict[tuple[int, tuple[str, ...]], float] = {}
        self._lock = threading.Lock()
        self.total_frames = 0
        self.total_inferences = 0
        self.total_events = 0
        self.last_person_count = 0
        self.last_detection_count = 0
        self.last_frame_shape: tuple[int, int] | None = None
        self.last_callback_ts: datetime | None = None
        self.last_inference_ts: datetime | None = None
        self.last_event_ts: datetime | None = None

    def process_frame(self, frame: Any) -> Any:
        timestamp = datetime.utcnow()
        with self._lock:
            self.frame_store.update_raw(self.camera_id, frame, timestamp)
            self.last_frame_ts = timestamp
            self.last_callback_ts = timestamp
            self.total_frames += 1
            self.last_frame_shape = tuple(frame.shape[:2]) if hasattr(frame, "shape") else None
            self.health = CameraHealth.ONLINE
            self._capture_count += 1
            self._update_capture_fps()

            if not self.scheduler.should_run():
                self._persist_status(active_tracks=len(self.tracker.list_active_tracks(self.camera_id)))
                return frame

            try:
                detections = self.yolo_engine.infer(frame)
            except Exception as exc:  # pragma: no cover - depends on env/model
                logger.exception("Browser inference failed for camera %s: %s", self.camera_id, exc)
                self.health = CameraHealth.DEGRADED
                self.status_message = str(exc)
                self._persist_status(active_tracks=len(self.tracker.list_active_tracks(self.camera_id)))
                return frame

            self.frame_store.update_annotated(self.camera_id, frame, timestamp)
            self._infer_count += 1
            self.total_inferences += 1
            self.last_inference_ts = timestamp
            self._update_inference_fps()
            if self.yolo_engine.last_load_error:
                self.status_message = (
                    f"{self.yolo_engine.last_load_error}. "
                    f"Fallback ativo: {self.yolo_engine.active_model_path}. "
                    "Deteccao de pessoa habilitada, mas eventos de EPI exigem pesos customizados."
                )
            elif not self.yolo_engine.supports_ppe():
                self.status_message = (
                    f"Modelo ativo: {self.yolo_engine.active_model_path}. "
                    "Classes de EPI nao encontradas; somente rastreamento de pessoa esta disponivel."
                )
            else:
                self.status_message = f"Modelo ativo: {self.yolo_engine.active_model_path}"
            person_detections = [item for item in detections if item.class_name == PERSON_CLASS and item.track_id is not None]
            self.last_detection_count = len(detections)
            self.last_person_count = len(person_detections)
            active_tracks = 0

            for person in person_detections:
                active_tracks += 1
                track = self.tracker.update_track(self.camera_id, person.track_id or 0, person.bbox, timestamp)
                if self.yolo_engine.supports_ppe():
                    association = associate_ppe(track, detections)
                    decision = self.compliance_engine.evaluate(
                        camera_id=self.camera_id,
                        track=track,
                        association=association,
                        required_ppe=self.config.required_ppe,
                        timestamp=timestamp,
                    )
                    self.latest_decision = decision.state
                    if decision.state == DecisionState.CONFIRMED_NON_COMPLIANCE and self._should_emit_event(decision, time.monotonic()):
                        self._emit_event(decision, timestamp)

            self._persist_status(active_tracks=active_tracks)
            annotated = self.frame_store.get_latest_annotated()
            return annotated.frame if annotated is not None else frame

    def get_status(self) -> CameraStatus:
        return CameraStatus(
            camera_id=self.camera_id,
            health=self.health,
            last_frame_ts=self.last_frame_ts,
            capture_fps=self.capture_fps,
            inference_fps=self.inference_fps,
            active_tracks=len(self.tracker.list_active_tracks(self.camera_id)),
            latest_decision=self.latest_decision,
            status_message=self.status_message,
            diagnostics={
                "total_frames": self.total_frames,
                "total_inferences": self.total_inferences,
                "total_events": self.total_events,
                "last_person_count": self.last_person_count,
                "last_detection_count": self.last_detection_count,
                "last_frame_shape": self.last_frame_shape,
                "last_callback_ts": self.last_callback_ts.isoformat() if self.last_callback_ts else None,
                "last_inference_ts": self.last_inference_ts.isoformat() if self.last_inference_ts else None,
                "last_event_ts": self.last_event_ts.isoformat() if self.last_event_ts else None,
                "model_path": self.yolo_engine.active_model_path,
                "supports_ppe": self.yolo_engine.supports_ppe(),
                "supports_person": self.yolo_engine.supports_person(),
                "load_error": self.yolo_engine.last_load_error,
            },
        )

    def list_active_tracks(self):
        return self.tracker.list_active_tracks(self.camera_id)

    def get_frame(self):
        return self.frame_store.get_latest_annotated() or self.frame_store.get_latest_raw()

    def _should_emit_event(self, decision, monotonic_now: float) -> bool:
        key = (decision.track_id, tuple(sorted(decision.missing_ppe)))
        last_emitted = self._event_history.get(key, 0.0)
        if monotonic_now - last_emitted < self.settings.event_cooldown_seconds:
            return False
        self._event_history[key] = monotonic_now
        return True

    def _emit_event(self, decision, timestamp: datetime) -> None:
        packet = self.frame_store.get_latest_annotated() or self.frame_store.get_latest_raw()
        if packet is None:
            return
        self.evidence_writer.enqueue(
            EvidenceJob(
                camera_name=self.config.name,
                decision=decision,
                frame_packet=packet,
                ring_buffer=self.frame_store.snapshot_buffer(),
            )
        )
        time.sleep(0.05)
        image_path, video_path = self.evidence_writer.get_paths(self.camera_id, decision.track_id)
        with get_session() as session:
            event = EventRepository(session).create(self.config.name, decision, image_path, video_path)
            session.commit()
            self.total_events += 1
            self.last_event_ts = datetime.utcnow()
            self.report_worker.enqueue(
                ReportJob(
                    event=EventView(
                        id=event.id,
                        camera_name=event.camera_name,
                        person_label=event.person_label,
                        decision_state=DecisionState(event.decision_state),
                        severity=EventSeverity(event.severity),
                        missing_ppe=event.missing_ppe.split(",") if event.missing_ppe else [],
                        confidence_score=event.confidence_score,
                        persistence_seconds=event.persistence_seconds,
                        rationale=event.rationale,
                        image_path=event.image_path,
                        video_path=event.video_path,
                        created_at=event.created_at,
                    )
                )
            )

    def _update_capture_fps(self) -> None:
        elapsed = time.monotonic() - self._capture_window_started
        if elapsed >= 1.0:
            self.capture_fps = self._capture_count / elapsed
            self._capture_count = 0
            self._capture_window_started = time.monotonic()

    def _update_inference_fps(self) -> None:
        elapsed = time.monotonic() - self._infer_window_started
        if elapsed >= 1.0:
            self.inference_fps = self._infer_count / elapsed
            self._infer_count = 0
            self._infer_window_started = time.monotonic()

    def _persist_status(self, active_tracks: int) -> None:
        with get_session() as session:
            CameraStatusRepository(session).upsert(
                camera_id=self.camera_id,
                health=self.health.value,
                last_frame_ts=self.last_frame_ts,
                capture_fps=self.capture_fps,
                inference_fps=self.inference_fps,
                active_tracks=active_tracks,
                latest_decision=self.latest_decision.value if self.latest_decision else None,
                status_message=self.status_message,
            )
            session.commit()
