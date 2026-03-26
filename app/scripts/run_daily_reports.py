from __future__ import annotations

from app.core.config import get_settings
from app.integrations.streamlit_contracts import OnSafeBackend
from app.storage.database import init_database


def main() -> None:
    settings = get_settings()
    init_database(settings.database_url)
    backend = OnSafeBackend(settings)
    path = backend.build_daily_report()
    print(path)


if __name__ == "__main__":
    main()
