from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import Settings
from app.core.enums import DecisionState
from app.core.schemas import EventView


class HtmlReportRenderer:
    def __init__(self, settings: Settings) -> None:
        template_dir = Path(__file__).resolve().parent / "html_templates"
        self.settings = settings
        self.environment = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(),
        )

    def render_event_report(self, event: EventView) -> str:
        template = self.environment.get_template("event_report.html")
        badge_class = "confirmed" if event.decision_state == DecisionState.CONFIRMED_NON_COMPLIANCE else "suspected"
        badge_label = "Confirmado" if badge_class == "confirmed" else "Duvidoso"
        image_uri = Path(event.image_path).resolve().as_uri() if event.image_path else None
        html = template.render(
            title=self.settings.report_title,
            event=event,
            badge_class=badge_class,
            badge_label=badge_label,
            image_uri=image_uri,
        )
        filename = f"event_{event.id}.html"
        output_path = Path(self.settings.reports_event_dir) / filename
        output_path.write_text(html, encoding="utf-8")
        return str(output_path)
