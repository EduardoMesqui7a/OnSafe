from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

from app.core.enums import CameraHealth
from app.core.schemas import CameraConfig
from app.pipeline.frame_store import FrameStore

logger = logging.getLogger(__name__)


class CameraReader:
    def __init__(self, camera_id: int, config: CameraConfig, frame_store: FrameStore, reconnect_delay_seconds: float) -> None:
        self.camera_id = camera_id
        self.config = config
        self.frame_store = frame_store
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.health = CameraHealth.STOPPED
        self.capture_fps = 0.0
        self.last_frame_ts: datetime | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name=f"camera-reader-{self.camera_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.health = CameraHealth.STOPPED

    def _run(self) -> None:
        if cv2 is None:
            self.health = CameraHealth.DEGRADED
            logger.warning("OpenCV is not available. Camera %s cannot start.", self.camera_id)
            return

        stream_url = self.config.build_stream_url()
        frames = 0
        window_start = time.monotonic()
        while not self._stop_event.is_set():
            capture = cv2.VideoCapture(stream_url)
            if not capture.isOpened():
                self.health = CameraHealth.OFFLINE
                time.sleep(self.reconnect_delay_seconds)
                continue
            self.health = CameraHealth.ONLINE
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok:
                    self.health = CameraHealth.DEGRADED
                    break
                now = datetime.utcnow()
                self.frame_store.update_raw(self.camera_id, frame, now)
                self.last_frame_ts = now
                frames += 1
                elapsed = time.monotonic() - window_start
                if elapsed >= 1.0:
                    self.capture_fps = frames / elapsed
                    frames = 0
                    window_start = time.monotonic()
            capture.release()
            time.sleep(self.reconnect_delay_seconds)
