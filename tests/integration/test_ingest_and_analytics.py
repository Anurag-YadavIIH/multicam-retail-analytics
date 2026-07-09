from datetime import UTC, datetime, timedelta

from tests.conftest import auth

WORKER = {"X-Worker-Key": "test-secret-key-for-pytest-0123456789ab"}


def _create_camera(client, token) -> int:
    return client.post(
        "/api/v1/cameras", headers=auth(token), json={"name": "cam", "source": "0", "type": "usb"}
    ).json()["id"]


def _ingest(client, cam_id: int, people: int = 3, queue: int = 7):
    ts = datetime.now(UTC).isoformat()
    return client.post(
        "/api/v1/ingest/frame",
        headers=WORKER,
        json={
            "camera_id": cam_id,
            "ts": ts,
            "fps": 4.8,
            "detections": [
                {
                    "class_name": "person",
                    "confidence": 0.9,
                    "bbox": [0.1, 0.1, 0.2, 0.4],
                    "track_id": i,
                }
                for i in range(people)
            ],
            "snapshot": {
                "people_count": people,
                "unique_visitors": people,
                "avg_dwell_s": 42.0,
                "queue_length": queue,
                "avg_wait_s": 30.0,
                "zone_occupancy": {"queue-1": queue},
            },
        },
    )


def test_ingest_requires_worker_key(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    resp = client.post(
        "/api/v1/ingest/frame",
        json={
            "camera_id": cam_id,
            "ts": datetime.now(UTC).isoformat(),
            "fps": 1.0,
            "detections": [],
        },
    )
    assert resp.status_code == 401


def test_ingest_creates_snapshot_and_alert(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    resp = _ingest(client, cam_id, queue=7)  # above the queue_length threshold -> high_queue alert
    assert resp.status_code == 200
    assert resp.json()["alerts"] >= 1

    alerts = client.get("/api/v1/alerts", headers=auth(admin_token)).json()
    assert any(a["type"] == "high_queue" for a in alerts)

    snaps = client.get(
        f"/api/v1/analytics/snapshots?camera_id={cam_id}&hours=1", headers=auth(admin_token)
    ).json()
    assert snaps and snaps[0]["queue_length"] == 7


def test_alert_dedup_within_window(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    first = _ingest(client, cam_id, queue=8).json()["alerts"]
    second = _ingest(client, cam_id, queue=9).json()["alerts"]
    assert first >= 1 and second == 0  # deduped


def test_overview_and_traffic(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    _ingest(client, cam_id, people=5, queue=1)
    overview = client.get("/api/v1/analytics/overview", headers=auth(admin_token)).json()
    assert overview["current_occupancy"] == 5
    traffic = client.get("/api/v1/analytics/traffic?hours=1", headers=auth(admin_token)).json()
    assert traffic[-1]["count"] == 5


def test_track_ingest_and_dwell(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    now = datetime.now(UTC)
    resp = client.post(
        "/api/v1/ingest/track",
        headers=WORKER,
        json={
            "camera_id": cam_id,
            "track_id": 11,
            "class_name": "person",
            "first_seen": (now - timedelta(minutes=2)).isoformat(),
            "last_seen": now.isoformat(),
            "duration_s": 120.0,
            "avg_speed_px_s": 12.5,
            "trajectory": [[0.1, 0.2, 0.0]],
            "zones_visited": ["entrance"],
        },
    )
    assert resp.status_code == 200
    dwell = client.get("/api/v1/analytics/dwell?hours=24", headers=auth(admin_token)).json()
    assert dwell["tracks"] == 1
