from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from app.core.schemas import TrackState, TrackView


class TrackerManager:
    def __init__(self, stale_after_seconds: int = 5) -> None:
        self._display_ids: dict[int, dict[int, int]] = defaultdict(dict)
        self._next_display_id: dict[int, int] = defaultdict(lambda: 1)
        self._track_states: dict[int, dict[int, TrackState]] = defaultdict(dict)
        self.stale_after = timedelta(seconds=stale_after_seconds)

    def update_track(self, camera_id: int, track_id: int, bbox: tuple[int, int, int, int], timestamp: datetime) -> TrackState:
        camera_tracks = self._track_states[camera_id]
        display_id = self._display_ids[camera_id].get(track_id)
        if display_id is None:
            display_id = self._next_display_id[camera_id]
            self._display_ids[camera_id][track_id] = display_id
            self._next_display_id[camera_id] += 1
        state = camera_tracks.get(track_id)
        if state is None:
            state = TrackState(
                camera_id=camera_id,
                track_id=track_id,
                display_person_id=display_id,
                label=f"Pessoa {display_id}",
                bbox=bbox,
                stability_hits=1,
                first_seen=timestamp,
                last_seen=timestamp,
            )
            camera_tracks[track_id] = state
            return state
        state.bbox = bbox
        state.stability_hits += 1
        state.last_seen = timestamp
        return state

    def list_active_tracks(self, camera_id: int, now: datetime | None = None) -> list[TrackView]:
        now = now or datetime.utcnow()
        active: list[TrackView] = []
        for track_id, state in list(self._track_states[camera_id].items()):
            if now - state.last_seen > self.stale_after:
                continue
            active.append(
                TrackView(
                    camera_id=camera_id,
                    label=state.label,
                    track_id=track_id,
                    bbox=state.bbox,
                    stability_hits=state.stability_hits,
                    last_seen=state.last_seen,
                )
            )
        return active

    def get_track(self, camera_id: int, track_id: int) -> TrackState | None:
        return self._track_states[camera_id].get(track_id)
