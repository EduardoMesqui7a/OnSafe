from __future__ import annotations

from app.storage.database import get_session
from app.storage.repositories import CameraRepository


class HealthService:
    def summary(self) -> dict[str, int]:
        with get_session() as session:
            cameras = CameraRepository(session).list()
            return {
                "registered_cameras": len(cameras),
            }
