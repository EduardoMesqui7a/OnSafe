from __future__ import annotations

from datetime import datetime

from app.pipeline.tracker_manager import TrackerManager


def test_tracker_manager_generates_stable_person_labels():
    manager = TrackerManager()
    now = datetime.utcnow()
    first = manager.update_track(1, 10, (0, 0, 10, 10), now)
    second = manager.update_track(1, 10, (1, 1, 11, 11), now)
    assert first.label == "Pessoa 1"
    assert second.stability_hits == 2
    active = manager.list_active_tracks(1, now)
    assert active[0].label == "Pessoa 1"
