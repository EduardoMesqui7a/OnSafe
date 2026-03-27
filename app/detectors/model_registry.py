from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ULTRALYTICS_IMPORT_ERROR: str | None = None

try:
    from ultralytics import YOLO
except Exception as exc:  # pragma: no cover - optional dependency
    YOLO = None
    ULTRALYTICS_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


@lru_cache(maxsize=4)
def load_model(model_path: str):
    if YOLO is None:
        details = f" Original import error: {ULTRALYTICS_IMPORT_ERROR}" if ULTRALYTICS_IMPORT_ERROR else ""
        raise RuntimeError(f"Ultralytics is not available in the current environment.{details}")
    if model_path.endswith(".pt") and not Path(model_path).exists():
        raise FileNotFoundError(f"Model weights not found: {model_path}")
    return YOLO(model_path)
