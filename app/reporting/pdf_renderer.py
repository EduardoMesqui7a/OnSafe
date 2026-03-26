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
        pdf_path = str(Path(html_path).with_suffix(".pdf"))
        HTML(filename=html_path).write_pdf(pdf_path)
        return pdf_path
