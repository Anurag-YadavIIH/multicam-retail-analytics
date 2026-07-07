"""Per-camera analytics engine.

Consumes tracked objects each frame and maintains:
  - people count / unique visitors / dwell
  - zone occupancy + queue length & estimated wait
  - shelf occupancy (product detections inside shelf zones) + empty detection
  - loitering + restricted-zone events
  - movement / footfall / queue / shelf heatmaps

Emits domain events + a periodic snapshot dict that the worker ships to the
backend. Pure python/numpy - unit-testable without any model.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from analytics.zones import ZoneDef, zones_containing
from tracking.track_store import TrackStore
from tracking.tracker import TrackedObject
from vision.heatmap import HeatmapAccumulator

LOITER_SECONDS = 120.0
SHELF_EMPTY_AFTER_S = 60.0


@dataclass
class EngineOutput:
    events: list[dict] = field(default_factory=list)
    snapshot: dict | None = None


class AnalyticsEngine:
    def __init__(
        self,
        camera_id: int,
        zones: list[ZoneDef],
        frame_size: tuple[int, int],
        snapshot_interval_s: float = 60.0,
    ) -> None:
        self.camera_id = camera_id
        self.zones = zones
        self.frame_w, self.frame_h = frame_size
        self.snapshot_interval_s = snapshot_interval_s
        self.store = TrackStore()
        self.heat_movement = HeatmapAccumulator()
        self.heat_footfall = HeatmapAccumulator(decay=0.999)
        self.heat_queue = HeatmapAccumulator()
        self.heat_shelf = HeatmapAccumulator()
        self._last_snapshot: datetime | None = None
        self._track_zones: dict[int, set[str]] = {}
        self._queue_joined_at: dict[int, datetime] = {}
        self._wait_samples: list[float] = []
        self._shelf_last_product: dict[str, datetime] = {}
        self._shelf_product_count: dict[str, int] = {}
        self._loiter_flagged: set[int] = set()
        self._restricted_flagged: set[int] = set()

    # ------------------------------------------------------------------ main
    def process(self, tracked: list[TrackedObject], now: datetime | None = None) -> EngineOutput:
        now = now or datetime.now(UTC)
        if self._last_snapshot is None:
            self._last_snapshot = now
        out = EngineOutput()
        people = [t for t in tracked if t.class_name == "person"]
        products = [t for t in tracked if t.class_name == "product"]

        zone_people: dict[str, int] = {z.name: 0 for z in self.zones}
        queue_len = 0

        for person in people:
            fx, fy = person.foot_point
            nx, ny = fx / self.frame_w, fy / self.frame_h
            in_zones = zones_containing(nx, ny, self.zones)
            zone_names = [z.name for z in in_zones]
            st = self.store.update(person.track_id, "person", (nx, ny), (fx, fy), zone_names, now)
            self.heat_movement.add_point(nx, ny)
            self.heat_footfall.add_point(nx, ny)

            prev = self._track_zones.get(person.track_id, set())
            cur = set(zone_names)
            for z in in_zones:
                if z.name not in prev:
                    out.events.append(self._event("zone_enter", now, person.track_id, z))
                    if z.type == "entrance":
                        out.events.append(self._event("entry", now, person.track_id, z))
                    if z.type == "queue":
                        self._queue_joined_at[person.track_id] = now
                        out.events.append(self._event("queue_join", now, person.track_id, z))
                    if z.type == "restricted" and person.track_id not in self._restricted_flagged:
                        self._restricted_flagged.add(person.track_id)
                        out.events.append(self._event("restricted_zone", now, person.track_id, z))
                if z.type == "queue":
                    queue_len += 1
                    self.heat_queue.add_point(nx, ny)
                if z.type == "shelf":
                    self.heat_shelf.add_point(nx, ny)
                    out.events.append(self._event("shelf_interaction", now, person.track_id, z))
                zone_people[z.name] = zone_people.get(z.name, 0) + 1
            for zname in prev - cur:
                zdef = next((z for z in self.zones if z.name == zname), None)
                out.events.append(self._event("zone_exit", now, person.track_id, zdef))
                if zdef is not None and zdef.type == "queue":
                    joined = self._queue_joined_at.pop(person.track_id, None)
                    if joined is not None:
                        self._wait_samples.append((now - joined).total_seconds())
                    out.events.append(self._event("queue_leave", now, person.track_id, zdef))
            self._track_zones[person.track_id] = cur

            if st.duration_s > LOITER_SECONDS and person.track_id not in self._loiter_flagged:
                self._loiter_flagged.add(person.track_id)
                out.events.append(
                    self._event(
                        "loitering",
                        now,
                        person.track_id,
                        None,
                        {"dwell_s": round(st.duration_s, 1)},
                    )
                )

        # shelf occupancy from product detections
        for z in self.zones:
            if z.type != "shelf":
                continue
            count = 0
            for p in products:
                cx = (p.bbox[0] + p.bbox[2]) / 2 / self.frame_w
                cy = (p.bbox[1] + p.bbox[3]) / 2 / self.frame_h
                if zones_containing(cx, cy, [z]):
                    count += 1
            prev_count = self._shelf_product_count.get(z.name, count)
            if count > 0:
                self._shelf_last_product[z.name] = now
            if count < prev_count:
                out.events.append(
                    self._event(
                        "shelf_interaction",
                        now,
                        None,
                        z,
                        {"change": "product_removed", "before": prev_count, "after": count},
                    )
                )
            elif count > prev_count:
                out.events.append(
                    self._event(
                        "shelf_interaction",
                        now,
                        None,
                        z,
                        {"change": "product_replaced", "before": prev_count, "after": count},
                    )
                )
            self._shelf_product_count[z.name] = count

        # expire tracks that left; count exits
        for gone in self.store.expire(now):
            out.events.append(
                {
                    "type": "exit",
                    "ts": now.isoformat(),
                    "track_id": gone.track_id,
                    "zone": None,
                    "payload": {"duration_s": round(gone.duration_s, 1)},
                    "closed_track": {
                        "camera_id": self.camera_id,
                        "track_id": gone.track_id,
                        "class_name": gone.class_name,
                        "first_seen": gone.first_seen.isoformat(),
                        "last_seen": gone.last_seen.isoformat(),
                        "duration_s": round(gone.duration_s, 1),
                        "avg_speed_px_s": round(gone.avg_speed_px_s, 1),
                        "trajectory": gone.trajectory,
                        "zones_visited": gone.zones_visited,
                    },
                }
            )
            self._track_zones.pop(gone.track_id, None)
            self._queue_joined_at.pop(gone.track_id, None)
            self._loiter_flagged.discard(gone.track_id)
            self._restricted_flagged.discard(gone.track_id)

        if (now - self._last_snapshot).total_seconds() >= self.snapshot_interval_s:
            out.snapshot = self._snapshot(len(people), queue_len, zone_people, now)
            self._last_snapshot = now
        return out

    # ---------------------------------------------------------------- helpers
    def _snapshot(
        self, people_count: int, queue_len: int, zone_people: dict[str, int], now: datetime
    ) -> dict:
        dwell = self.store.dwell_times()
        avg_wait = (
            sum(self._wait_samples[-50:]) / len(self._wait_samples[-50:])
            if self._wait_samples
            else 0.0
        )
        shelf_empty = [
            name
            for name, last in self._shelf_last_product.items()
            if (now - last).total_seconds() > SHELF_EMPTY_AFTER_S
        ]
        return {
            "people_count": people_count,
            "unique_visitors": self.store.total_unique,
            "avg_dwell_s": round(sum(dwell) / len(dwell), 1) if dwell else 0.0,
            "queue_length": queue_len,
            "avg_wait_s": round(avg_wait, 1),
            "zone_occupancy": zone_people,
            "shelf_empty": shelf_empty,
        }

    def _event(
        self,
        type_: str,
        now: datetime,
        track_id: int | None,
        zone: ZoneDef | None,
        payload: dict | None = None,
    ) -> dict:
        return {
            "type": type_,
            "ts": now.isoformat(),
            "track_id": track_id,
            "zone": zone.name if zone else None,
            "zone_id": zone.id if zone else None,
            "payload": payload or {},
        }
