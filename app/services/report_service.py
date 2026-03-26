from __future__ import annotations

from app.core.schemas import ReportRecord
from app.reporting.daily_report_builder import DailyReportBuilder
from app.storage.database import get_session
from app.storage.repositories import ReportRepository


class ReportService:
    def __init__(self, daily_builder: DailyReportBuilder) -> None:
        self.daily_builder = daily_builder

    def build_daily_report(self) -> str:
        return self.daily_builder.build_for_today()

    def list_reports(self, limit: int = 100) -> list[ReportRecord]:
        with get_session() as session:
            return [ReportRecord.model_validate(item) for item in ReportRepository(session).list_recent(limit=limit)]
