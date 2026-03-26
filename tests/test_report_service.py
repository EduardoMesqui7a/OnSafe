from __future__ import annotations

from app.core.schemas import CameraConfig, ComplianceDecision
from app.core.config import Settings
from app.core.enums import DecisionState
from app.reporting.daily_report_builder import DailyReportBuilder
from app.services.camera_service import CameraService
from app.services.report_service import ReportService
from app.storage.database import get_session, init_database
from app.storage.repositories import EventRepository


def test_report_service_builds_daily_report(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'onsafe.db'}",
        data_dir=tmp_path,
        evidence_image_dir=tmp_path / "images",
        evidence_video_dir=tmp_path / "videos",
        reports_event_dir=tmp_path / "reports_events",
        reports_daily_dir=tmp_path / "reports_daily",
    )
    settings.ensure_directories()
    init_database(settings.database_url)
    camera = CameraService().register_camera(CameraConfig(name="Linha 1", host="10.0.0.30", port=554))
    decision = ComplianceDecision(
        camera_id=camera.id,
        track_id=12,
        person_label="Pessoa 2",
        state=DecisionState.CONFIRMED_NON_COMPLIANCE,
        missing_ppe=["vest"],
        confidence_score=0.91,
        persistence_seconds=4.0,
        valid_inferences=5,
        rationale="Teste relatorio",
    )
    with get_session() as session:
        EventRepository(session).create("Linha 1", decision, None, None)
        session.commit()
    service = ReportService(DailyReportBuilder(settings))
    path = service.build_daily_report()
    assert path.endswith(".html")
