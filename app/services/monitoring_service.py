from __future__ import annotations

from app.core.enums import CameraHealth
from app.core.schemas import CameraConfig, CameraStatus, OperationResult, TrackView
from app.pipeline.monitor_manager import MonitorManager
from app.services.camera_service import CameraService


class MonitoringService:
    def __init__(self, monitor_manager: MonitorManager, camera_service: CameraService) -> None:
        self.monitor_manager = monitor_manager
        self.camera_service = camera_service
        self._registered_runtime_ids: set[int] = set()

    def start_monitoring(self, camera_id: int) -> OperationResult:
        camera = self.camera_service.get_camera(camera_id)
        if camera is None:
            return OperationResult(success=False, message="Camera nao encontrada.")
        if camera_id not in self._registered_runtime_ids:
            config = CameraConfig(
                name=camera.name,
                host=camera.host,
                port=camera.port,
                username=camera.username,
                password=camera.password,
                protocol=camera.protocol,
                stream_path=camera.stream_path,
                enabled=camera.enabled,
                required_ppe=camera.required_ppe,
            )
            self.monitor_manager.register_camera(camera_id, config)
            self._registered_runtime_ids.add(camera_id)
        self.monitor_manager.start_camera(camera_id)
        return OperationResult(success=True, message=f"Monitoramento iniciado para camera {camera.name}.")

    def register_browser_runtime(self, camera_id: int) -> None:
        self._registered_runtime_ids.add(camera_id)

    def stop_monitoring(self, camera_id: int) -> OperationResult:
        if camera_id not in self._registered_runtime_ids:
            return OperationResult(success=True, message=f"Camera {camera_id} ja estava parada.")
        self.monitor_manager.stop_camera(camera_id)
        return OperationResult(success=True, message=f"Monitoramento parado para camera {camera_id}.")

    def get_camera_status(self, camera_id: int) -> CameraStatus:
        if camera_id not in self._registered_runtime_ids:
            return CameraStatus(camera_id=camera_id, health=CameraHealth.STOPPED)
        return self.monitor_manager.get_status(camera_id)

    def get_live_snapshot(self, camera_id: int):
        if camera_id not in self._registered_runtime_ids:
            return None
        return self.monitor_manager.get_frame(camera_id)

    def list_active_tracks(self, camera_id: int) -> list[TrackView]:
        if camera_id not in self._registered_runtime_ids:
            return []
        return self.monitor_manager.list_active_tracks(camera_id)
