from __future__ import annotations

from app.core.config import get_settings
from app.core.schemas import CameraConfig
from app.integrations.streamlit_contracts import OnSafeBackend
from app.storage.database import init_database


def main() -> None:
    settings = get_settings()
    init_database(settings.database_url)
    backend = OnSafeBackend(settings)
    sample = CameraConfig(name="Camera Demo", host="127.0.0.1", port=554, stream_path="stream")
    camera = backend.register_camera(sample)
    print(f"Camera registrada: {camera.id} - {camera.name}")
    print(backend.test_camera(sample).model_dump())


if __name__ == "__main__":
    main()
