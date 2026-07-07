from datetime import UTC, datetime, timedelta

from tracking.track_store import TrackStore


def t(seconds: float) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)


def test_unique_counting_and_dwell():
    store = TrackStore(ttl_s=5)
    store.update(1, "person", (0.5, 0.5), (100, 100), [], now=t(0))
    store.update(1, "person", (0.6, 0.5), (200, 100), [], now=t(10))
    store.update(2, "person", (0.1, 0.1), (10, 10), [], now=t(10))
    assert store.total_unique == 2
    assert store.tracks[1].duration_s == 10.0


def test_speed_accumulates_distance():
    store = TrackStore()
    store.update(1, "person", (0, 0), (0, 0), [], now=t(0))
    store.update(1, "person", (0, 0), (30, 40), [], now=t(10))  # 50px moved
    assert abs(store.tracks[1].avg_speed_px_s - 5.0) < 1e-6


def test_expiry_returns_closed_tracks():
    store = TrackStore(ttl_s=5)
    store.update(1, "person", (0.5, 0.5), (1, 1), [], now=t(0))
    store.update(2, "person", (0.5, 0.5), (1, 1), [], now=t(8))
    gone = store.expire(now=t(9))
    assert [g.track_id for g in gone] == [1]
    assert list(store.tracks) == [2]


def test_zone_visits_deduplicated():
    store = TrackStore()
    store.update(1, "person", (0.5, 0.5), (1, 1), ["queue"], now=t(0))
    store.update(1, "person", (0.5, 0.5), (1, 1), ["queue", "aisle"], now=t(1))
    assert store.tracks[1].zones_visited == ["queue", "aisle"]
