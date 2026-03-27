from __future__ import annotations

import base64
from datetime import timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
        image_uri = self._build_embedded_image_uri(event.image_path)
        annotated_image_uri = self._build_embedded_image_uri(self._get_annotated_image_path(event.image_path))
        missing_ppe_labels = self._format_ppe_list(event.missing_ppe)
        occurred_at = self._format_datetime(event.created_at)
        html = template.render(
            title=self.settings.report_title,
            event=event,
            badge_class=badge_class,
            badge_label=badge_label,
            image_uri=image_uri,
            annotated_image_uri=annotated_image_uri,
            missing_ppe_labels=missing_ppe_labels,
            occurred_at=occurred_at,
        )
        filename = f"event_{event.id}.html"
        output_path = Path(self.settings.reports_event_dir) / filename
        output_path.write_text(html, encoding="utf-8")
        return str(output_path)

    def _build_embedded_image_uri(self, image_path: str | None) -> str | None:
        if not image_path:
            return None
        path = Path(image_path)
        if not path.exists():
            return None
        suffix = path.suffix.lower()
        mime = "image/png"
        if suffix in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _format_ppe_list(self, items: list[str]) -> str:
        labels = {"helmet": "capacete", "vest": "colete"}
        return ", ".join(labels.get(item, item) for item in items) if items else "n/a"

    def _format_datetime(self, value) -> str:
        if value is None:
            return "n/a"
        local_timezone = self._get_local_timezone()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(local_timezone).strftime("%d/%m/%Y %H:%M:%S")

    def _get_annotated_image_path(self, image_path: str | None) -> str | None:
        if not image_path:
            return None
        path = Path(image_path)
        return str(path.with_name(f"{path.stem}_anotada{path.suffix}"))

    def _get_local_timezone(self):
        try:
            return ZoneInfo(self.settings.timezone_name)
        except ZoneInfoNotFoundError:
            return timezone(timedelta(hours=-3))
