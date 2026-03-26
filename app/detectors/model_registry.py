from __future__ import annotations

from functools import lru_cache
from pathlib import Path

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - optional dependency
    YOLO = None


@lru_cache(maxsize=4)
def load_model(model_path: str):
    if YOLO is None:
        raise RuntimeError("Ultralytics is not available in the current environment.")
    if model_path.endswith(".pt") and not Path(model_path).exists():
        raise FileNotFoundError(f"Model weights not found: {model_path}")
    return YOLO(model_path)
