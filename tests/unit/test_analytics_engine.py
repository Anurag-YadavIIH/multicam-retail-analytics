from datetime import UTC, datetime, timedelta

from analytics.engine import AnalyticsEngine
from analytics.zones import ZoneDef
from tracking.tracker import TrackedObject


def t(seconds: float) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)


def person(track_id: int, cx: float, cy: float) -> TrackedObject:
    # 1000x1000 frame; bbox whose foot point (bottom-center) lands at (cx, cy)
    return TrackedObject(
        track_id, "person", 0.9, (cx * 1000 - 20, cy * 1000 - 100, cx * 1000 + 20, cy * 1000)
    )


def make_engine(snapshot_interval_s: float = 1.0) -> AnalyticsEngine:
    zones = [
        ZoneDef(1, "entrance", "entrance", ((0.0, 0.0), (0.3, 0.0), (0.3, 1.0), (0.0, 1.0))),
        ZoneDef(2, "queue-1", "queue", ((0.6, 0.0), (1.0, 0.0), (1.0, 1.0), (0.6, 1.0))),
        ZoneDef(3, "vault", "restricted", ((0.4, 0.0), (0.55, 0.0), (0.55, 0.3), (0.4, 0.3))),
    ]
    return AnalyticsEngine(1, zones, (1000, 1000), snapshot_interval_s=snapshot_interval_s)


def test_entry_event_and_zone_enter():
    eng = make_engine()
    out = eng.process([person(1, 0.1, 0.5)], now=t(0))
    types = [e["type"] for e in out.events]
    assert "zone_enter" in types
    assert "entry" in types


def test_queue_length_and_wait():
    eng = make_engine(snapshot_interval_s=0.5)
    eng.process([person(1, 0.7, 0.5), person(2, 0.8, 0.5)], now=t(0))
    out = eng.process([person(1, 0.7, 0.5), person(2, 0.8, 0.5)], now=t(60))
    assert out.snapshot is not None
    assert out.snapshot["queue_length"] == 2
    # person 1 leaves the queue -> wait sample recorded
    out2 = eng.process([person(1, 0.1, 0.5), person(2, 0.8, 0.5)], now=t(90))
    assert any(e["type"] == "queue_leave" for e in out2.events)


def test_restricted_zone_event_fires_once():
    eng = make_engine()
    out1 = eng.process([person(1, 0.5, 0.1)], now=t(0))
    out2 = eng.process([person(1, 0.5, 0.1)], now=t(1))
    r1 = [e for e in out1.events if e["type"] == "restricted_zone"]
    r2 = [e for e in out2.events if e["type"] == "restricted_zone"]
    assert len(r1) == 1 and len(r2) == 0


def test_exit_produces_closed_track():
    eng = make_engine()
    eng.process([person(1, 0.1, 0.5)], now=t(0))
    out = eng.process([], now=t(30))  # ttl 10s -> expired
    exits = [e for e in out.events if e["type"] == "exit"]
    assert len(exits) == 1
    closed = exits[0]["closed_track"]
    assert closed["track_id"] == 1
    assert closed["zones_visited"] == ["entrance"]


def test_snapshot_counts_unique_visitors():
    eng = make_engine(snapshot_interval_s=1.0)
    eng.process([person(1, 0.1, 0.5)], now=t(0))
    out = eng.process([person(1, 0.1, 0.5), person(2, 0.7, 0.5)], now=t(61))
    assert out.snapshot is not None
    assert out.snapshot["unique_visitors"] == 2
    assert out.snapshot["people_count"] == 2
