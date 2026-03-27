from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.constants import (
    DEFAULT_FRAME_QUEUE_SIZE,
    DEFAULT_INFERENCE_FPS,
    DEFAULT_PREVIEW_FPS,
    DEFAULT_RING_BUFFER_SECONDS,
)


class Settings(BaseModel):
    project_name: str = "OnSafe"
    base_dir: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    database_url: str = "sqlite:///data/db/onsafe.db"
    evidence_image_dir: Path = Path("data/evidence/images")
    evidence_video_dir: Path = Path("data/evidence/videos")
    reports_event_dir: Path = Path("data/reports/events")
    reports_daily_dir: Path = Path("data/reports/daily")
    preview_fps: int = DEFAULT_PREVIEW_FPS
    inference_fps: int = DEFAULT_INFERENCE_FPS
    frame_queue_size: int = DEFAULT_FRAME_QUEUE_SIZE
    ring_buffer_seconds: int = DEFAULT_RING_BUFFER_SECONDS
    inference_image_size: int = 640
    save_event_video: bool = False
    event_video_fps: int = 6
    post_event_seconds: int = 5
    event_cooldown_seconds: int = 15
    reconnect_delay_seconds: float = 2.0
    max_test_frames: int = 5
    report_title: str = "OnSafe - Relatório Técnico de EPI"
    timezone_name: str = "America/Sao_Paulo"

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.evidence_image_dir,
            self.evidence_video_dir,
            self.reports_event_dir,
            self.reports_daily_dir,
            Path("data/db"),
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
