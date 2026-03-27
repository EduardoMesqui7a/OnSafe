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
        annotated_path = self._get_annotated_path(path)
        cv2.imwrite(str(annotated_path), self._build_annotated_frame(job))
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

    def _build_annotated_frame(self, job: EvidenceJob):
        frame = job.frame_packet.frame.copy()
        bbox = job.decision.track_bbox
        if bbox is None:
            return frame

        x1, y1, x2, y2 = bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 99, 132), 2)
        cv2.putText(
            frame,
            job.decision.person_label,
            (x1, max(28, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 99, 132),
            2,
            cv2.LINE_AA,
        )

        if "helmet" in job.decision.missing_ppe:
            hx1, hy1, hx2, hy2 = self._head_region(bbox)
            cv2.rectangle(frame, (hx1, hy1), (hx2, hy2), (255, 255, 255), 2)
            cv2.putText(
                frame,
                "Sem capacete",
                (hx1, max(24, hy1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        if "vest" in job.decision.missing_ppe:
            tx1, ty1, tx2, ty2 = self._torso_region(bbox)
            cv2.rectangle(frame, (tx1, ty1), (tx2, ty2), (0, 255, 255), 2)
            cv2.putText(
                frame,
                "Sem colete",
                (tx1, max(24, ty1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

        alerts: list[str] = []
        if "helmet" in job.decision.missing_ppe:
            alerts.append("sem capacete")
        if "vest" in job.decision.missing_ppe:
            alerts.append("sem colete")
        if alerts:
            cv2.putText(
                frame,
                f"ALERTA: {', '.join(alerts)}",
                (16, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        return frame

    def _head_region(self, person_box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        px1, py1, px2, py2 = person_box
        pw = px2 - px1
        ph = py2 - py1
        return (
            int(px1 + 0.10 * pw),
            int(py1),
            int(px2 - 0.10 * pw),
            int(py1 + 0.32 * ph),
        )

    def _torso_region(self, person_box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        px1, py1, px2, py2 = person_box
        pw = px2 - px1
        ph = py2 - py1
        return (
            int(px1 + 0.12 * pw),
            int(py1 + 0.28 * ph),
            int(px2 - 0.12 * pw),
            int(py1 + 0.80 * ph),
        )

    def _get_annotated_path(self, image_path: Path) -> Path:
        return image_path.with_name(f"{image_path.stem}_anotada{image_path.suffix}")
