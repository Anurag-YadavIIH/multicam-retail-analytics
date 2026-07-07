"""Privacy: blur faces before any frame leaves the worker.

Strategy: pixelate the head region (top ~22%) of each person bbox. This is
model-free, fast on CPU, and errs on the side of blurring more than needed -
GDPR-friendly default for retail deployments.
"""

import numpy as np

HEAD_FRACTION = 0.22
PIXEL_BLOCK = 12


def blur_faces(
    frame: np.ndarray, person_boxes: list[tuple[float, float, float, float]]
) -> np.ndarray:
    """Pixelate the head region of each person bbox (pixel coords, xyxy). In-place."""
    h, w = frame.shape[:2]
    for x1, y1, x2, y2 in person_boxes:
        xi1, yi1 = max(int(x1), 0), max(int(y1), 0)
        xi2 = min(int(x2), w)
        head_y2 = min(int(y1 + (y2 - y1) * HEAD_FRACTION), h)
        if xi2 - xi1 < 4 or head_y2 - yi1 < 4:
            continue
        roi = frame[yi1:head_y2, xi1:xi2]
        rh, rw = roi.shape[:2]
        small = roi[:: max(rh // PIXEL_BLOCK, 1), :: max(rw // PIXEL_BLOCK, 1)]
        frame[yi1:head_y2, xi1:xi2] = np.kron(
            small, np.ones((-(-rh // small.shape[0]), -(-rw // small.shape[1]), 1), dtype=np.uint8)
        )[:rh, :rw]
    return frame
