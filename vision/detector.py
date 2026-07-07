"""YOLO detector wrapper.

- Loads Ultralytics YOLO (yolo11n by default; swap any .pt/.onnx/.engine path).
- Maps raw model classes to retail domain classes via configs/classes.yaml.
- Supports CPU, CUDA, batch inference and ONNX Runtime models transparently
  (ultralytics dispatches on file extension).

For true retail classes (shopping_cart, shelf, checkout_counter, staff) fine-tune
on your store footage / SKU-110K - see docs/TRAINING.md. Out of the box the COCO
mapping below gives a working person/product pipeline.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml


@dataclass(frozen=True)
class DetectionResult:
    """One detection in pixel xyxy coords."""

    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]


DEFAULT_CLASS_MAP: dict[str, str] = {
    # COCO class -> retail domain class
    "person": "person",
    "backpack": "basket",
    "handbag": "basket",
    "suitcase": "cart",
    "bottle": "product",
    "cup": "product",
    "banana": "product",
    "apple": "product",
    "orange": "product",
    "book": "product",
    "cell phone": "product",
}


def load_class_map(path: str | Path = "configs/classes.yaml") -> dict[str, str]:
    p = Path(path)
    if p.exists():
        data = yaml.safe_load(p.read_text()) or {}
        mapping = data.get("class_map")
        if isinstance(mapping, dict) and mapping:
            return {str(k): str(v) for k, v in mapping.items()}
    return dict(DEFAULT_CLASS_MAP)


class YoloDetector:
    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        device: str = "cpu",
        conf: float = 0.35,
        iou: float = 0.5,
        class_map: dict[str, str] | None = None,
    ) -> None:
        from ultralytics import YOLO  # deferred: heavy import

        self.model = YOLO(model_path)
        self.device = device
        self.conf = conf
        self.iou = iou
        self.class_map = class_map or load_class_map()
        self.names: dict[int, str] = dict(self.model.names)

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        return self.detect_batch([frame])[0]

    def detect_batch(self, frames: list[np.ndarray]) -> list[list[DetectionResult]]:
        """Batch inference - one forward pass for N frames (GPU efficient)."""
        results = self.model.predict(
            frames,
            device=self.device,
            conf=self.conf,
            iou=self.iou,
            verbose=False,
            half=self.device.startswith("cuda"),
        )
        out: list[list[DetectionResult]] = []
        for res in results:
            dets: list[DetectionResult] = []
            if res.boxes is not None:
                for box in res.boxes:
                    raw = self.names[int(box.cls.item())]
                    mapped = self.class_map.get(raw)
                    if mapped is None:
                        continue  # ignore classes outside the retail domain
                    x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
                    dets.append(DetectionResult(mapped, float(box.conf.item()), (x1, y1, x2, y2)))
            out.append(dets)
        return out

    def export_onnx(self, out_dir: str = "models") -> str:
        """Export to ONNX for onnxruntime / edge deployment."""
        path = self.model.export(format="onnx", dynamic=True, simplify=True)
        return str(Path(path).rename(Path(out_dir) / Path(path).name))
