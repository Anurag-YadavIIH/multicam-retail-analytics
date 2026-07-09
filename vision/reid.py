"""On-worker Re-ID embedding extraction: OSNet (osnet_x0_25) via ONNX
Runtime, CPU-only. See docs/REID.md for the model/heuristic/pipeline design.

Fails soft throughout - a missing/broken model, or a failure on one crop,
must never take down the tracking pipeline (mirrors DetectionProducer's
disabled-when-unavailable pattern in streaming/kafka_client.py).
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)

INPUT_HEIGHT, INPUT_WIDTH = 256, 128  # OSNet's expected person-crop size
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
MIN_CROP_CONFIDENCE = 0.5  # floor for "best crop" candidacy - see docs/REID.md


def bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(x2 - x1, 0.0) * max(y2 - y1, 0.0)


def crop_bbox(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray:
    """Pixel-coord xyxy crop, clamped to the frame bounds."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    xi1, yi1 = max(int(x1), 0), max(int(y1), 0)
    xi2, yi2 = min(int(x2), w), min(int(y2), h)
    return frame[yi1:yi2, xi1:xi2]


def preprocess(crop_bgr: np.ndarray) -> np.ndarray:
    """BGR pixel crop -> OSNet's expected (1, 3, 256, 128) float32 NCHW batch."""
    resized = cv2.resize(crop_bgr, (INPUT_WIDTH, INPUT_HEIGHT))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    normalized = (rgb - IMAGENET_MEAN) / IMAGENET_STD
    chw = normalized.transpose(2, 0, 1)
    return chw[np.newaxis, ...].astype(np.float32)


class ReidExtractor:
    """Wraps an ONNX Runtime session for osnet_x0_25. Disabled (not an
    error) if the model file is missing or fails to load - `.enabled` is
    False and `.extract()` becomes a no-op returning None."""

    def __init__(self, model_path: str) -> None:
        self.session = None
        self.input_name: str | None = None
        try:
            import onnxruntime as ort

            self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
        except Exception:
            logger.warning("Re-ID model unavailable at %s - extraction disabled", model_path)

    @property
    def enabled(self) -> bool:
        return self.session is not None

    @property
    def output_dim(self) -> int | None:
        """Model's embedding dim (last axis of its output shape), or None if
        disabled. Lets callers - namely scripts/calibrate_reid.py - assert
        this matches the 512 that vision/reid.py and the /ingest/reid schema
        both assume, before trusting anything extracted through this session."""
        if not self.enabled:
            return None
        dim = self.session.get_outputs()[0].shape[-1]
        return dim if isinstance(dim, int) else None

    def extract(self, crop_bgr: np.ndarray) -> list[float] | None:
        """512-dim, L2-normalized embedding for one person crop, or None if
        disabled or this crop fails to process."""
        if not self.enabled or crop_bgr.size == 0:
            return None
        try:
            batch = preprocess(crop_bgr)
            (output,) = self.session.run(None, {self.input_name: batch})
            vector = output[0].astype(np.float64)
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            return vector.tolist()
        except Exception:
            logger.exception("Re-ID extraction failed for one crop - skipping")
            return None
