from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

from app.core.config import Settings
from app.core.schemas import ComplianceDecision, FramePacket


@dataclass(slots=True)
class EvidenceJob:
    camera_name: str
    decision: ComplianceDecision
    frame_packet: FramePacket
    ring_buffer: list[FramePacket]


class EvidenceWriter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs: queue.Queue[EvidenceJob] = queue.Queue(maxsize=64)
        self._thread = threading.Thread(target=self._run, name="evidence-writer", daemon=True)
        self._started = False
        self._results: dict[tuple[int, int], tuple[str | None, str | None]] = {}

    def start(self) -> None:
        if not self._started:
            self._thread.start()
            self._started = True

    def enqueue(self, job: EvidenceJob) -> None:
        self.start()
        self.jobs.put_nowait(job)

    def get_paths(self, camera_id: int, track_id: int) -> tuple[str | None, str | None]:
        return self._results.get((camera_id, track_id), (None, None))

    def _run(self) -> None:
        while True:
            job = self.jobs.get()
            image_path = self._save_image(job)
            video_path = self._save_video(job) if self.settings.save_event_video else None
            self._results[(job.decision.camera_id, job.decision.track_id)] = (image_path, video_path)
            self.jobs.task_done()

    def _save_image(self, job: EvidenceJob) -> str | None:
        if cv2 is None:
            return None
        timestamp = job.frame_packet.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"camera_{job.decision.camera_id}_track_{job.decision.track_id}_{timestamp}.jpg"
        path = Path(self.settings.evidence_image_dir) / filename
        cv2.imwrite(str(path), job.frame_packet.frame)
        return str(path)

    def _save_video(self, job: EvidenceJob) -> str | None:
        if cv2 is None or not job.ring_buffer:
            return None
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"camera_{job.decision.camera_id}_track_{job.decision.track_id}_{timestamp}.mp4"
        path = Path(self.settings.evidence_video_dir) / filename
        first_frame = job.ring_buffer[0].frame
        height, width = first_frame.shape[:2]
        writer = cv2.VideoWriter(
            str(path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            float(self.settings.event_video_fps),
            (width, height),
        )
        for packet in job.ring_buffer:
            writer.write(packet.frame)
        writer.release()
        return str(path)
