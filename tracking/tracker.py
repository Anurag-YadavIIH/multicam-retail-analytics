"""ByteTrack multi-object tracking via the supervision library.

Wraps supervision.ByteTrack so the rest of the codebase only deals with the
simple TrackedObject dataclass (easy to unit-test and to swap for BoT-SORT /
DeepSORT later).
"""

from dataclasses import dataclass

import numpy as np

from vision.detector import DetectionResult


@dataclass(frozen=True)
class TrackedObject:
    track_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # pixel xyxy

    @property
    def foot_point(self) -> tuple[float, float]:
        """Bottom-center of bbox - the point standing on the floor plane."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, y2)


class ByteTracker:
    """persistent-ID tracker. lost_track_buffer keeps IDs alive across short
    occlusions (lost-track recovery)."""

    def __init__(
        self,
        fps: int = 5,
        track_activation_threshold: float = 0.25,
        lost_track_buffer: int = 60,
        min_matching_threshold: float = 0.8,
    ) -> None:
        import supervision as sv

        self._sv = sv
        self.tracker = sv.ByteTrack(
            track_activation_threshold=track_activation_threshold,
            lost_track_buffer=lost_track_buffer,
            minimum_matching_threshold=min_matching_threshold,
            frame_rate=fps,
        )
        self._class_ids: dict[str, int] = {}
        self._class_names: dict[int, str] = {}

    def _class_id(self, name: str) -> int:
        if name not in self._class_ids:
            idx = len(self._class_ids)
            self._class_ids[name] = idx
            self._class_names[idx] = name
        return self._class_ids[name]

    def update(self, detections: list[DetectionResult]) -> list[TrackedObject]:
        sv = self._sv
        if not detections:
            dets = sv.Detections.empty()
        else:
            dets = sv.Detections(
                xyxy=np.array([d.bbox for d in detections], dtype=np.float32),
                confidence=np.array([d.confidence for d in detections], dtype=np.float32),
                class_id=np.array([self._class_id(d.class_name) for d in detections]),
            )
        tracked = self.tracker.update_with_detections(dets)
        out: list[TrackedObject] = []
        if tracked.tracker_id is None:
            return out
        for i in range(len(tracked)):
            out.append(
                TrackedObject(
                    track_id=int(tracked.tracker_id[i]),
                    class_name=self._class_names[int(tracked.class_id[i])],
                    confidence=(
                        float(tracked.confidence[i]) if tracked.confidence is not None else 0.0
                    ),
                    bbox=tuple(float(v) for v in tracked.xyxy[i]),
                )
            )
        return out
