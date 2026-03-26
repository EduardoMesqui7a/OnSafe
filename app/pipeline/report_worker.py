from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

from app.core.config import Settings
from app.core.enums import ReportKind, ReportStatus
from app.core.schemas import EventView
from app.reporting.html_renderer import HtmlReportRenderer
from app.reporting.pdf_renderer import PdfReportRenderer
from app.storage.database import get_session
from app.storage.repositories import ReportRepository


@dataclass(slots=True)
class ReportJob:
    event: EventView


class ReportWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.jobs: queue.Queue[ReportJob] = queue.Queue(maxsize=64)
        self.html_renderer = HtmlReportRenderer(settings)
        self.pdf_renderer = PdfReportRenderer()
        self._thread = threading.Thread(target=self._run, name="report-worker", daemon=True)
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._thread.start()
            self._started = True

    def enqueue(self, job: ReportJob) -> None:
        self.start()
        self.jobs.put_nowait(job)

    def _run(self) -> None:
        while True:
            job = self.jobs.get()
            html_path = self.html_renderer.render_event_report(job.event)
            pdf_path = self.pdf_renderer.render_pdf_from_html(html_path)
            with get_session() as session:
                ReportRepository(session).create(
                    report_kind=ReportKind.EVENT.value,
                    status=ReportStatus.GENERATED.value,
                    title=f"Evento {job.event.id} - {job.event.camera_name}",
                    html_path=html_path,
                    pdf_path=pdf_path,
                )
                session.commit()
            self.jobs.task_done()
