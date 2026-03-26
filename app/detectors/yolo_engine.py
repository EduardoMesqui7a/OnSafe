from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.detectors.class_map import SUPPORTED_CLASSES
from app.detectors.model_registry import load_model


@dataclass(slots=True)
class Detection:
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]
    track_id: int | None = None


class YoloEngine:
    def __init__(self, model_path: str, image_size: int = 640, tracker_config: str = "bytetrack.yaml") -> None:
        self.model_path = model_path
        self.image_size = image_size
        self.tracker_config = tracker_config
        self._model = None

    def _get_model(self):
        if self._model is None:
            self._model = load_model(self.model_path)
        return self._model

    def infer(self, frame: Any) -> list[Detection]:
        model = self._get_model()
        results = model.track(frame, persist=True, imgsz=self.image_size, tracker=self.tracker_config, verbose=False)
        if not results:
            return []
        detections: list[Detection] = []
        result = results[0]
        names = getattr(result, "names", {})
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return detections
        xyxy = boxes.xyxy.int().tolist()
        conf = boxes.conf.tolist()
        cls = boxes.cls.int().tolist()
        ids = boxes.id.int().tolist() if boxes.id is not None else [None] * len(xyxy)
        for bbox, score, cls_idx, track_id in zip(xyxy, conf, cls, ids):
            class_name = names.get(cls_idx, str(cls_idx))
            if class_name not in SUPPORTED_CLASSES:
                continue
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=float(score),
                    bbox=tuple(int(value) for value in bbox),
                    track_id=int(track_id) if track_id is not None else None,
                )
            )
        return detections
