from __future__ import annotations

from datetime import date
from pathlib import Path

from app.core.config import Settings
from app.core.enums import ReportKind, ReportStatus
from app.storage.database import get_session
from app.storage.repositories import EventRepository, ReportRepository


class DailyReportBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_for_today(self) -> str:
        today = date.today().isoformat()
        with get_session() as session:
            events = EventRepository(session).list_recent(limit=500)
            lines = [
                "<html><body>",
                f"<h1>{self.settings.project_name} - Consolidado Diario {today}</h1>",
                "<table border='1' cellspacing='0' cellpadding='8'>",
                "<tr><th>Horario</th><th>Camera</th><th>Pessoa</th><th>Estado</th><th>EPI Ausente</th><th>Confianca</th></tr>",
            ]
            for event in events:
                lines.append(
                    "<tr>"
                    f"<td>{event.created_at}</td>"
                    f"<td>{event.camera_name}</td>"
                    f"<td>{event.person_label}</td>"
                    f"<td>{event.decision_state}</td>"
                    f"<td>{event.missing_ppe}</td>"
                    f"<td>{event.confidence_score:.2f}</td>"
                    "</tr>"
                )
            lines.extend(["</table>", "</body></html>"])
            output_path = Path(self.settings.reports_daily_dir) / f"daily_{today}.html"
            output_path.write_text("\n".join(lines), encoding="utf-8")
            ReportRepository(session).create(
                report_kind=ReportKind.DAILY.value,
                status=ReportStatus.GENERATED.value,
                title=f"Consolidado diario {today}",
                html_path=str(output_path),
                pdf_path=None,
            )
            session.commit()
            return str(output_path)
