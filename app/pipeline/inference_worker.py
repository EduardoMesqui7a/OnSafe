from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime

from app.core.enums import CameraHealth, DecisionState, EventSeverity
from app.core.schemas import CameraConfig, EventView
from app.detectors.class_map import PERSON_CLASS
from app.detectors.yolo_engine import YoloEngine
from app.pipeline.compliance_engine import ComplianceEngine
from app.pipeline.evidence_writer import EvidenceJob, EvidenceWriter
from app.pipeline.frame_store import FrameStore
from app.pipeline.ppe_association import associate_ppe
from app.pipeline.report_worker import ReportJob, ReportWorker
from app.pipeline.tracker_manager import TrackerManager
from app.storage.database import get_session
from app.storage.repositories import CameraStatusRepository, EventRepository

logger = logging.getLogger(__name__)


class InferenceWorker:
    def __init__(
        self,
        camera_id: int,
        config: CameraConfig,
        frame_store: FrameStore,
        tracker: TrackerManager,
        compliance_engine: ComplianceEngine,
        yolo_engine: YoloEngine,
        evidence_writer: EvidenceWriter,
        report_worker: ReportWorker,
    ) -> None:
        self.camera_id = camera_id
        self.config = config
        self.frame_store = frame_store
        self.tracker = tracker
        self.compliance_engine = compliance_engine
        self.yolo_engine = yolo_engine
        self.evidence_writer = evidence_writer
        self.report_worker = report_worker
        self._thread = threading.Thread(target=self._run, name=f"inference-{camera_id}", daemon=True)
        self._stop_event = threading.Event()
        self._trigger = queue.Queue(maxsize=1)
        self._last_processed_ts: datetime | None = None
        self._event_history: dict[tuple[int, tuple[str, ...]], float] = {}
        self.inference_fps = 0.0
        self.latest_decision: DecisionState | None = None
        self.status_message: str | None = None

    def start(self) -> None:
        if not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name=f"inference-{self.camera_id}", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def trigger(self) -> None:
        try:
            self._trigger.put_nowait(True)
        except queue.Full:
            return

    def _run(self) -> None:
        processed = 0
        window_start = time.monotonic()
        while not self._stop_event.is_set():
            try:
                self._trigger.get(timeout=0.25)
            except queue.Empty:
                continue
            packet = self.frame_store.get_latest_raw()
            if packet is None or self._last_processed_ts == packet.timestamp:
                continue
            self._last_processed_ts = packet.timestamp
            try:
                detections = self.yolo_engine.infer(packet.frame)
            except Exception as exc:  # pragma: no cover - depends on env/model
                logger.exception("Inference failed for camera %s: %s", self.camera_id, exc)
                self.status_message = str(exc)
                with get_session() as session:
                    CameraStatusRepository(session).upsert(
                        camera_id=self.camera_id,
                        health=CameraHealth.DEGRADED.value,
                        last_frame_ts=packet.timestamp,
                        inference_fps=self.inference_fps,
                        active_tracks=0,
                        latest_decision=self.latest_decision.value if self.latest_decision else None,
                        status_message=self.status_message,
                    )
                    session.commit()
                continue

            self.frame_store.update_annotated(self.camera_id, packet.frame, packet.timestamp)
            processed += 1
            elapsed = time.monotonic() - window_start
            if elapsed >= 1.0:
                self.inference_fps = processed / elapsed
                processed = 0
                window_start = time.monotonic()
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

            active_tracks = 0
            latest_decision = None
            person_detections = [item for item in detections if item.class_name == PERSON_CLASS and item.track_id is not None]
            for person in person_detections:
                active_tracks += 1
                track = self.tracker.update_track(self.camera_id, person.track_id or 0, person.bbox, packet.timestamp)
                if self.yolo_engine.supports_ppe():
                    association = associate_ppe(track, detections)
                    latest_decision = self.compliance_engine.evaluate(
                        camera_id=self.camera_id,
                        track=track,
                        association=association,
                        required_ppe=self.config.required_ppe,
                        timestamp=packet.timestamp,
                    )
                    self.latest_decision = latest_decision.state
                    if (
                        latest_decision.state == DecisionState.CONFIRMED_NON_COMPLIANCE
                        and self._should_emit_event(latest_decision, time.monotonic())
                    ):
                        self.evidence_writer.enqueue(
                            EvidenceJob(
                                camera_name=self.config.name,
                                decision=latest_decision,
                                frame_packet=packet,
                                ring_buffer=self.frame_store.snapshot_buffer(),
                            )
                        )
                        time.sleep(0.05)
                        image_path, video_path = self.evidence_writer.get_paths(self.camera_id, latest_decision.track_id)
                        with get_session() as session:
                            event = EventRepository(session).create(self.config.name, latest_decision, image_path, video_path)
                            session.commit()
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
            with get_session() as session:
                CameraStatusRepository(session).upsert(
                    camera_id=self.camera_id,
                    health=CameraHealth.ONLINE.value,
                    last_frame_ts=packet.timestamp,
                    inference_fps=self.inference_fps,
                    active_tracks=active_tracks,
                    latest_decision=self.latest_decision.value if self.latest_decision else None,
                    status_message=self.status_message,
                )
                session.commit()

    def _should_emit_event(self, decision, monotonic_now: float) -> bool:
        key = (decision.track_id, tuple(sorted(decision.missing_ppe)))
        last_emitted = self._event_history.get(key, 0.0)
        if monotonic_now - last_emitted < 15.0:
            return False
        self._event_history[key] = monotonic_now
        return True
