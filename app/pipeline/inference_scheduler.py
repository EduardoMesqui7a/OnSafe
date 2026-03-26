from __future__ import annotations

import time


class InferenceScheduler:
    def __init__(self, target_fps: int) -> None:
        self.min_interval = 1.0 / max(target_fps, 1)
        self._last_run = 0.0

    def should_run(self) -> bool:
        now = time.monotonic()
        if now - self._last_run < self.min_interval:
            return False
        self._last_run = now
        return True
