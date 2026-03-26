from __future__ import annotations

from functools import lru_cache

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - optional dependency
    YOLO = None


@lru_cache(maxsize=4)
def load_model(model_path: str):
    if YOLO is None:
        raise RuntimeError("Ultralytics is not available in the current environment.")
    return YOLO(model_path)
