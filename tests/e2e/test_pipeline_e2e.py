"""End-to-end pipeline test: synthetic detections -> tracker-shaped objects ->
analytics engine -> ingest API -> analytics API. Runs without torch by
simulating tracked objects moving through zones over time."""

from datetime import UTC, datetime, timedelta

from analytics.engine import AnalyticsEngine
from analytics.zones import ZoneDef
from tests.conftest import auth
from tracking.tracker import TrackedObject

WORKER = {"X-Worker-Key": "test-secret-key-for-pytest-0123456789ab"}


def test_full_journey(client, admin_token):
    cam = client.post(
        "/api/v1/cameras",
        headers=auth(admin_token),
        json={
            "name": "e2e",
            "source": "0",
            "type": "usb",
        },
    ).json()
    zones = [
        ZoneDef(1, "entrance", "entrance", ((0, 0.5), (0.3, 0.5), (0.3, 1), (0, 1))),
        ZoneDef(2, "queue", "queue", ((0.6, 0.0), (1, 0.0), (1, 1), (0.6, 1))),
    ]
    engine = AnalyticsEngine(cam["id"], zones, (1000, 1000), snapshot_interval_s=30)

    t0 = datetime.now(UTC) - timedelta(minutes=30)
    # a shopper walks: entrance (x=0.1) -> aisle (x=0.45) -> queue (x=0.8) -> gone
    path = [0.1, 0.2, 0.45, 0.6, 0.8, 0.85]
    all_events = []
    snapshot = None
    for i, x in enumerate(path):
        obj = TrackedObject(1, "person", 0.9, (x * 1000 - 20, 500, x * 1000 + 20, 800))
        out = engine.process([obj], now=t0 + timedelta(seconds=i * 10))
        all_events += out.events
        snapshot = out.snapshot or snapshot
    out = engine.process([], now=t0 + timedelta(seconds=200))  # shopper leaves
    all_events += out.events

    types = {e["type"] for e in all_events}
    assert {"entry", "zone_enter", "queue_join", "exit"} <= types

    closed = next(e["closed_track"] for e in all_events if e["type"] == "exit")
    resp = client.post("/api/v1/ingest/track", headers=WORKER, json=closed)
    assert resp.status_code == 200
    assert snapshot is not None and snapshot["unique_visitors"] == 1

    dwell = client.get("/api/v1/analytics/dwell?hours=24", headers=auth(admin_token)).json()
    assert dwell["tracks"] == 1
    assert dwell["avg_dwell_s"] > 0
