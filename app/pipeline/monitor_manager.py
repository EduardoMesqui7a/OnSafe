from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.core.enums import CameraHealth
from app.core.schemas import CameraConfig, CameraStatus
from app.detectors.yolo_engine import YoloEngine
from app.pipeline.camera_reader import CameraReader
from app.pipeline.browser_runtime import BrowserCameraRuntime
from app.pipeline.compliance_engine import ComplianceEngine
from app.pipeline.evidence_writer import EvidenceWriter
from app.pipeline.frame_store import FrameStore
from app.pipeline.inference_scheduler import InferenceScheduler
from app.pipeline.inference_worker import InferenceWorker
from app.pipeline.report_worker import ReportWorker
from app.pipeline.tracker_manager import TrackerManager


@dataclass(slots=True)
class RuntimeBundle:
    frame_store: FrameStore
    reader: CameraReader
    scheduler: InferenceScheduler
    worker: InferenceWorker
    tracker: TrackerManager


class MonitorManager:
    def __init__(self, settings: Settings, model_path: str = "ppe.pt") -> None:
        self.settings = settings
        self.model_path = model_path
        self.evidence_writer = EvidenceWriter(settings)
        self.report_worker = ReportWorker(settings)
        self._bundles: dict[int, RuntimeBundle] = {}
        self._browser_runtimes: dict[int, BrowserCameraRuntime] = {}
        self._tick_thread = threading.Thread(target=self._tick, name="monitor-tick", daemon=True)
        self._stop_event = threading.Event()
        self._tick_started = False

    def register_camera(self, camera_id: int, config: CameraConfig) -> None:
        frame_store = FrameStore(self.settings.ring_buffer_seconds, self.settings.preview_fps)
        tracker = TrackerManager()
        worker = InferenceWorker(
            camera_id=camera_id,
            config=config,
            frame_store=frame_store,
            tracker=tracker,
            compliance_engine=ComplianceEngine(),
            yolo_engine=YoloEngine(self.model_path, self.settings.inference_image_size),
            evidence_writer=self.evidence_writer,
            report_worker=self.report_worker,
        )
        reader = CameraReader(camera_id, config, frame_store, self.settings.reconnect_delay_seconds)
        scheduler = InferenceScheduler(self.settings.inference_fps)
        self._bundles[camera_id] = RuntimeBundle(frame_store, reader, scheduler, worker, tracker)

    def start_camera(self, camera_id: int) -> None:
        if camera_id in self._browser_runtimes:
            return
        bundle = self._bundles[camera_id]
        bundle.reader.start()
        bundle.worker.start()
        if not self._tick_started:
            self._stop_event.clear()
            self._tick_thread = threading.Thread(target=self._tick, name="monitor-tick", daemon=True)
            self._tick_thread.start()
            self._tick_started = True

    def stop_camera(self, camera_id: int) -> None:
        if camera_id in self._browser_runtimes:
            return
        bundle = self._bundles[camera_id]
        bundle.reader.stop()
        bundle.worker.stop()

    def stop_all(self) -> None:
        for camera_id in list(self._bundles):
            self.stop_camera(camera_id)
        self._stop_event.set()
        self._tick_started = False

    def get_frame(self, camera_id: int):
        browser_runtime = self._browser_runtimes.get(camera_id)
        if browser_runtime is not None:
            return browser_runtime.get_frame()
        bundle = self._bundles.get(camera_id)
        if bundle is None:
            return None
        return bundle.frame_store.get_latest_annotated() or bundle.frame_store.get_latest_raw()

    def get_status(self, camera_id: int) -> CameraStatus:
        browser_runtime = self._browser_runtimes.get(camera_id)
        if browser_runtime is not None:
            return browser_runtime.get_status()
        bundle = self._bundles[camera_id]
        return CameraStatus(
            camera_id=camera_id,
            health=bundle.reader.health if bundle.reader.health else CameraHealth.STOPPED,
            last_frame_ts=bundle.reader.last_frame_ts,
            capture_fps=bundle.reader.capture_fps,
            inference_fps=bundle.worker.inference_fps,
            active_tracks=len(bundle.tracker.list_active_tracks(camera_id)),
            latest_decision=bundle.worker.latest_decision,
            status_message=bundle.worker.status_message,
            diagnostics={
                "total_inferences": bundle.worker.total_inferences,
                "total_events": bundle.worker.total_events,
                "last_person_count": bundle.worker.last_person_count,
                "last_detection_count": bundle.worker.last_detection_count,
                "last_inference_ts": bundle.worker.last_inference_ts.isoformat() if bundle.worker.last_inference_ts else None,
                "model_path": bundle.worker.yolo_engine.active_model_path,
                "supports_ppe": bundle.worker.yolo_engine.supports_ppe(),
                "supports_person": bundle.worker.yolo_engine.supports_person(),
                "load_error": bundle.worker.yolo_engine.last_load_error,
            },
        )

    def list_active_tracks(self, camera_id: int):
        browser_runtime = self._browser_runtimes.get(camera_id)
        if browser_runtime is not None:
            return browser_runtime.list_active_tracks()
        bundle = self._bundles[camera_id]
        return bundle.tracker.list_active_tracks(camera_id)

    def get_browser_runtime(self, camera_id: int, config: CameraConfig) -> BrowserCameraRuntime:
        runtime = self._browser_runtimes.get(camera_id)
        if runtime is None:
            runtime = BrowserCameraRuntime(
                camera_id=camera_id,
                config=config,
                settings=self.settings,
                evidence_writer=self.evidence_writer,
                report_worker=self.report_worker,
                model_path=self.model_path,
            )
            self._browser_runtimes[camera_id] = runtime
        return runtime

    def _tick(self) -> None:
        while not self._stop_event.is_set():
            for bundle in self._bundles.values():
                if bundle.scheduler.should_run():
                    bundle.worker.trigger()
            time.sleep(0.01)
