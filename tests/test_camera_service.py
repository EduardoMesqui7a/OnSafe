from __future__ import annotations

import pytest

from app.core.schemas import CameraConfig
from app.services.camera_service import CameraService
from app.storage.database import init_database


def test_register_and_list_camera(tmp_path):
    init_database(f"sqlite:///{tmp_path / 'onsafe.db'}")
    service = CameraService()
    record = service.register_camera(
        CameraConfig(
            name="Portaria",
            host="10.0.0.10",
            port=554,
            username="admin",
            password="123",
            stream_path="live",
        )
    )
    cameras = service.list_cameras()
    assert record.id > 0
    assert len(cameras) == 1
    assert cameras[0].required_ppe == ["helmet", "vest"]
    assert cameras[0].build_stream_url() == "rtsp://admin:123@10.0.0.10:554/live"


def test_camera_config_host_zero_maps_to_local_device():
    config = CameraConfig(
        name="Notebook",
        host="0",
        port=554,
        stream_path="ignored",
    )
    assert config.uses_local_device() is True
    assert config.get_capture_source() == 0
    assert config.build_stream_url() == "local://0"


def test_camera_config_browser_mode_uses_streamlit_source():
    config = CameraConfig(
        name="Browser",
        host="__browser__",
        port=0,
        stream_path="",
    )
    assert config.uses_browser_input() is True
    assert config.build_stream_url() == "browser://camera"


def test_register_camera_with_duplicate_name_raises_clear_error(tmp_path):
    init_database(f"sqlite:///{tmp_path / 'onsafe.db'}")
    service = CameraService()
    config = CameraConfig(name="Notebook", host="__browser__", port=0)
    service.register_camera(config)
    with pytest.raises(ValueError, match="Ja existe uma camera cadastrada"):
        service.register_camera(config)
