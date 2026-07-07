"""Annotated JPEG encoding for the live-preview / snapshot endpoints.

Draws on a copy of the frame so the caller's original array (e.g. the one used
as the heatmap background) is never mutated.
"""

from typing import Protocol

import cv2
import numpy as np

BOX_COLOR = (0, 200, 255)  # amber, BGR
LABEL_TEXT_COLOR = (10, 10, 10)
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.45


class Annotatable(Protocol):
    track_id: int
    class_name: str
    bbox: tuple[float, float, float, float]


def annotate(frame: np.ndarray, tracked: list[Annotatable]) -> np.ndarray:
    """Draw a box + "class #id" label per tracked object on a copy of frame."""
    out = frame.copy()
    for t in tracked:
        x1, y1, x2, y2 = (int(v) for v in t.bbox)
        cv2.rectangle(out, (x1, y1), (x2, y2), BOX_COLOR, 2)
        label = f"{t.class_name} #{t.track_id}"
        (tw, th), _ = cv2.getTextSize(label, FONT, FONT_SCALE, 1)
        label_y1 = max(y1 - th - 6, 0)
        cv2.rectangle(out, (x1, label_y1), (x1 + tw + 4, y1), BOX_COLOR, -1)
        cv2.putText(out, label, (x1 + 2, max(y1 - 4, th)), FONT, FONT_SCALE, LABEL_TEXT_COLOR, 1)
    return out


def encode_jpeg(frame: np.ndarray, quality: int = 70) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("failed to encode frame as JPEG")
    return buf.tobytes()
