from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import Settings
from app.core.enums import ReportKind, ReportStatus
from app.storage.database import get_session
from app.storage.repositories import EventRepository, ReportRepository


class DailyReportBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        template_dir = Path(__file__).resolve().parent / "html_templates"
        self.environment = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(),
        )

    def build_for_today(self) -> str:
        today = date.today().isoformat()
        with get_session() as session:
            events = EventRepository(session).list_recent(limit=500)
            template = self.environment.get_template("daily_report.html")
            html = template.render(
                title=f"{self.settings.project_name} - Consolidado Diário",
                report_date=today,
                events=events,
                total_events=len(events),
            )
            output_path = Path(self.settings.reports_daily_dir) / f"daily_{today}.html"
            output_path.write_text(html, encoding="utf-8")
            ReportRepository(session).create(
                report_kind=ReportKind.DAILY.value,
                status=ReportStatus.GENERATED.value,
                title=f"Consolidado diário {today}",
                html_path=str(output_path),
                pdf_path=None,
            )
            session.commit()
            return str(output_path)
