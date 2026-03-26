from __future__ import annotations

import time

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency
    cv2 = None

from app.core.enums import CameraHealth
from app.core.schemas import CameraConfig, CameraRecord, CameraTestResult
from app.storage.database import get_session
from app.storage.repositories import CameraRepository


class CameraService:
    def register_camera(self, config: CameraConfig) -> CameraRecord:
        with get_session() as session:
            model = CameraRepository(session).create(config)
            session.commit()
            session.refresh(model)
            return CameraRecord.model_validate(model)

    def list_cameras(self) -> list[CameraRecord]:
        with get_session() as session:
            return [CameraRecord.model_validate(item) for item in CameraRepository(session).list()]

    def get_camera(self, camera_id: int) -> CameraRecord | None:
        with get_session() as session:
            model = CameraRepository(session).get(camera_id)
            return CameraRecord.model_validate(model) if model else None

    def test_camera(self, config: CameraConfig) -> CameraTestResult:
        stream_url = config.build_stream_url()
        if config.uses_browser_input():
            return CameraTestResult(
                success=True,
                status=CameraHealth.ONLINE,
                message="Webcam do navegador deve ser validada diretamente na interface Streamlit.",
                stream_url=stream_url,
            )
        capture_source = config.get_capture_source()
        if cv2 is None:
            return CameraTestResult(
                success=False,
                status=CameraHealth.DEGRADED,
                message="OpenCV nao esta disponivel neste ambiente.",
                stream_url=stream_url,
            )
        started = time.perf_counter()
        capture = cv2.VideoCapture(capture_source)
        if not capture.isOpened():
            return CameraTestResult(
                success=False,
                status=CameraHealth.OFFLINE,
                message="Nao foi possivel abrir a camera local." if config.uses_local_device() else "Nao foi possivel abrir o stream.",
                stream_url=stream_url,
            )
        ok, _ = capture.read()
        capture.release()
        latency_ms = (time.perf_counter() - started) * 1000
        return CameraTestResult(
            success=ok,
            status=CameraHealth.ONLINE if ok else CameraHealth.DEGRADED,
            message="Camera local acessivel." if ok and config.uses_local_device() else "Stream acessivel." if ok else "Conexao aberta, mas sem leitura de frame.",
            latency_ms=latency_ms,
            stream_url=stream_url,
        )
