from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Lock
from typing import Any

from app.core.schemas import FramePacket


class FrameStore:
    def __init__(self, buffer_seconds: int, fps_hint: int) -> None:
        self._lock = Lock()
        self._latest_raw: FramePacket | None = None
        self._latest_annotated: FramePacket | None = None
        self._ring_buffer: deque[FramePacket] = deque(maxlen=max(1, buffer_seconds * max(fps_hint, 1)))

    def update_raw(self, camera_id: int, frame: Any, timestamp: datetime) -> None:
        packet = FramePacket(camera_id=camera_id, frame=frame, timestamp=timestamp, annotated=False)
        with self._lock:
            self._latest_raw = packet
            self._ring_buffer.append(packet)

    def update_annotated(self, camera_id: int, frame: Any, timestamp: datetime) -> None:
        packet = FramePacket(camera_id=camera_id, frame=frame, timestamp=timestamp, annotated=True)
        with self._lock:
            self._latest_annotated = packet

    def get_latest_raw(self) -> FramePacket | None:
        with self._lock:
            return self._latest_raw

    def get_latest_annotated(self) -> FramePacket | None:
        with self._lock:
            return self._latest_annotated

    def snapshot_buffer(self) -> list[FramePacket]:
        with self._lock:
            return list(self._ring_buffer)
