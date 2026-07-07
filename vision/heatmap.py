"""Heatmap accumulation + PNG rendering.

Accumulates foot-position points on a fixed grid; renders with a JET colormap
over an optional background frame. Used for movement, footfall, shelf
interaction and queue heatmaps (same accumulator, different point sources).
"""

from pathlib import Path

import numpy as np


class HeatmapAccumulator:
    def __init__(self, grid_w: int = 96, grid_h: int = 54, decay: float = 1.0) -> None:
        self.grid = np.zeros((grid_h, grid_w), dtype=np.float64)
        self.decay = decay  # 1.0 = no decay; <1.0 = recency-weighted heatmap

    def add_point(self, x_norm: float, y_norm: float, weight: float = 1.0) -> None:
        """Add a normalized [0,1] point (typically bbox bottom-center = feet)."""
        gh, gw = self.grid.shape
        gx = min(int(x_norm * gw), gw - 1)
        gy = min(int(y_norm * gh), gh - 1)
        if self.decay < 1.0:
            self.grid *= self.decay
        self.grid[gy, gx] += weight

    def normalized(self) -> np.ndarray:
        m = self.grid.max()
        return self.grid / m if m > 0 else self.grid

    def render_png(
        self, out_path: str | Path, background: np.ndarray | None = None, alpha: float = 0.55
    ) -> Path:
        import cv2

        heat = self.normalized()
        if background is not None:
            h, w = background.shape[:2]
        else:
            h, w = heat.shape[0] * 10, heat.shape[1] * 10
        heat_img = cv2.resize((heat * 255).astype(np.uint8), (w, h))
        heat_img = cv2.GaussianBlur(heat_img, (31, 31), 0)
        colored = cv2.applyColorMap(heat_img, cv2.COLORMAP_JET)
        if background is not None:
            colored = cv2.addWeighted(background, 1 - alpha, colored, alpha, 0)
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), colored)
        return out
