from __future__ import annotations

from app.storage.database import init_database


def run_migrations(database_url: str) -> None:
    init_database(database_url)
