from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
        local_timezone = self._get_local_timezone()
        today = datetime.now(local_timezone).date().isoformat()
        with get_session() as session:
            events = EventRepository(session).list_recent(limit=500)
            template = self.environment.get_template("daily_report.html")
            html = template.render(
                title=f"{self.settings.project_name} - Consolidado Diário",
                report_date=today,
                events=[
                    {
                        "created_at": self._format_datetime(event.created_at),
                        "camera_name": event.camera_name,
                        "person_label": event.person_label,
                        "decision_state": self._format_decision_state(event.decision_state),
                        "missing_ppe": self._format_ppe_list(event.missing_ppe),
                        "confidence_score": event.confidence_score,
                        "persistence_seconds": event.persistence_seconds,
                    }
                    for event in events
                ],
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

    def _format_datetime(self, value: datetime) -> str:
        local_timezone = self._get_local_timezone()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(local_timezone).strftime("%d/%m/%Y %H:%M:%S")

    def _format_ppe_list(self, items: list[str]) -> str:
        labels = {"helmet": "capacete", "vest": "colete"}
        return ", ".join(labels.get(item, item) for item in items) if items else "n/a"

    def _format_decision_state(self, value) -> str:
        raw = value.value if hasattr(value, "value") else str(value)
        labels = {
            "compliant": "Conforme",
            "suspected_non_compliance": "Não conformidade suspeita",
            "confirmed_non_compliance": "Não conformidade confirmada",
            "discarded_due_to_uncertainty": "Descartado por incerteza",
        }
        return labels.get(raw, raw)

    def _get_local_timezone(self):
        try:
            return ZoneInfo(self.settings.timezone_name)
        except ZoneInfoNotFoundError:
            return timezone(timedelta(hours=-3))
