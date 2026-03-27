from __future__ import annotations

from app.core.config import Settings
from app.core.schemas import CameraConfig, CameraStatus, CameraTestResult, EventView, OperationResult, ReportRecord, TrackView
from app.pipeline.monitor_manager import MonitorManager
from app.reporting.daily_report_builder import DailyReportBuilder
from app.services.camera_service import CameraService
from app.services.event_service import EventService
from app.services.health_service import HealthService
from app.services.monitoring_service import MonitoringService
from app.services.report_service import ReportService
from app.storage.database import init_database


class OnSafeBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        init_database(settings.database_url)
        self.camera_service = CameraService()
        self.monitor_manager = MonitorManager(settings)
        self.monitoring_service = MonitoringService(self.monitor_manager, self.camera_service)
        self.event_service = EventService()
        self.report_service = ReportService(DailyReportBuilder(settings))
        self.health_service = HealthService()

    def list_cameras(self):
        return self.camera_service.list_cameras()

    def register_camera(self, config: CameraConfig):
        return self.camera_service.register_camera(config)

    def test_camera(self, config: CameraConfig) -> CameraTestResult:
        return self.camera_service.test_camera(config)

    def start_monitoring(self, camera_id: int) -> OperationResult:
        return self.monitoring_service.start_monitoring(camera_id)

    def stop_monitoring(self, camera_id: int) -> OperationResult:
        return self.monitoring_service.stop_monitoring(camera_id)

    def get_camera_status(self, camera_id: int) -> CameraStatus:
        return self.monitoring_service.get_camera_status(camera_id)

    def get_live_snapshot(self, camera_id: int):
        return self.monitoring_service.get_live_snapshot(camera_id)

    def list_active_tracks(self, camera_id: int) -> list[TrackView]:
        return self.monitoring_service.list_active_tracks(camera_id)

    def list_recent_events(self, limit: int = 100) -> list[EventView]:
        return self.event_service.list_recent_events(limit=limit)

    def list_reports(self, limit: int = 100) -> list[ReportRecord]:
        return self.report_service.list_reports(limit=limit)

    def build_daily_report(self) -> str:
        return self.report_service.build_daily_report()

    def get_browser_runtime(self, camera_id: int):
        camera = self.camera_service.get_camera(camera_id)
        if camera is None:
            raise ValueError("Camera nao encontrada.")
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
        runtime = self.monitor_manager.get_browser_runtime(camera_id, config)
        self.monitoring_service.register_browser_runtime(camera_id)
        return runtime
