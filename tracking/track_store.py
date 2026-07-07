"""Track lifecycle bookkeeping: trajectory, speed, dwell, zone visits.

Pure-python + numpy (no cv2/torch) so it is fully unit-testable.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

MAX_TRAJECTORY_POINTS = 120  # downsampled history kept per track


@dataclass
class TrackState:
    track_id: int
    class_name: str
    first_seen: datetime
    last_seen: datetime
    trajectory: list[tuple[float, float, float]] = field(default_factory=list)  # x,y,t_offset
    zones_visited: list[str] = field(default_factory=list)
    _dist_px: float = 0.0
    _last_px: tuple[float, float] | None = None

    @property
    def duration_s(self) -> float:
        return max((self.last_seen - self.first_seen).total_seconds(), 0.0)

    @property
    def avg_speed_px_s(self) -> float:
        d = self.duration_s
        return self._dist_px / d if d > 0 else 0.0


class TrackStore:
    """Holds active tracks for one camera; expires them after `ttl_s` silence."""

    def __init__(self, ttl_s: float = 10.0) -> None:
        self.ttl_s = ttl_s
        self.tracks: dict[int, TrackState] = {}
        self.total_unique: int = 0

    def update(
        self,
        track_id: int,
        class_name: str,
        foot_norm: tuple[float, float],
        foot_px: tuple[float, float],
        zones: list[str],
        now: datetime | None = None,
    ) -> TrackState:
        now = now or datetime.now(UTC)
        st = self.tracks.get(track_id)
        if st is None:
            st = TrackState(track_id, class_name, first_seen=now, last_seen=now)
            self.tracks[track_id] = st
            self.total_unique += 1
        st.last_seen = now
        if st._last_px is not None:
            dx = foot_px[0] - st._last_px[0]
            dy = foot_px[1] - st._last_px[1]
            st._dist_px += (dx * dx + dy * dy) ** 0.5
        st._last_px = foot_px
        if len(st.trajectory) < MAX_TRAJECTORY_POINTS:
            st.trajectory.append(
                (
                    round(foot_norm[0], 4),
                    round(foot_norm[1], 4),
                    round((now - st.first_seen).total_seconds(), 2),
                )
            )
        for z in zones:
            if z not in st.zones_visited:
                st.zones_visited.append(z)
        return st

    def expire(self, now: datetime | None = None) -> list[TrackState]:
        """Remove and return tracks not seen for ttl_s (they left the scene)."""
        now = now or datetime.now(UTC)
        gone = [
            st for st in self.tracks.values() if (now - st.last_seen).total_seconds() > self.ttl_s
        ]
        for st in gone:
            del self.tracks[st.track_id]
        return gone

    def dwell_times(self, class_name: str = "person") -> list[float]:
        return [t.duration_s for t in self.tracks.values() if t.class_name == class_name]
