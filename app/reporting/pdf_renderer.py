from __future__ import annotations

from pathlib import Path

try:
    from weasyprint import HTML
except Exception:  # pragma: no cover - optional dependency
    HTML = None


class PdfReportRenderer:
    def render_pdf_from_html(self, html_path: str) -> str | None:
        if HTML is None:
            return None
        html_file = Path(html_path)
        pdf_path = str(html_file.with_suffix(".pdf"))
        HTML(filename=str(html_file), base_url=str(html_file.parent)).write_pdf(pdf_path)
        return pdf_path
