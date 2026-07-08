from datetime import UTC, datetime

from tests.conftest import auth

WORKER = {"X-Worker-Key": "test-secret-key-for-pytest-0123456789ab"}
EMBEDDING = [0.1] * 512


def _create_camera(client, token) -> int:
    return client.post(
        "/api/v1/cameras", headers=auth(token), json={"name": "cam", "source": "0", "type": "usb"}
    ).json()["id"]


def _create_track(client, cam_id: int, track_id: int = 1) -> None:
    now = datetime.now(UTC).isoformat()
    resp = client.post(
        "/api/v1/ingest/track",
        headers=WORKER,
        json={
            "camera_id": cam_id,
            "track_id": track_id,
            "class_name": "person",
            "first_seen": now,
            "last_seen": now,
            "duration_s": 5.0,
            "avg_speed_px_s": 1.0,
            "trajectory": [],
            "zones_visited": [],
        },
    )
    assert resp.status_code == 200


def test_ingest_reid_stores_embedding_and_creates_identity(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    _create_track(client, cam_id)

    resp = client.post(
        "/api/v1/ingest/reid",
        headers=WORKER,
        json={"camera_id": cam_id, "track_id": 1, "embedding": EMBEDDING},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["identity_id"], int)


def test_ingest_reid_matches_similar_embedding_to_same_identity(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    _create_track(client, cam_id, track_id=1)
    _create_track(client, cam_id, track_id=2)
    vec_a = [1.0] + [0.0] * 511

    first = client.post(
        "/api/v1/ingest/reid",
        headers=WORKER,
        json={"camera_id": cam_id, "track_id": 1, "embedding": vec_a},
    )
    second = client.post(
        "/api/v1/ingest/reid",
        headers=WORKER,
        json={"camera_id": cam_id, "track_id": 2, "embedding": vec_a},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["identity_id"] == first.json()["identity_id"]


def test_ingest_reid_creates_separate_identity_for_dissimilar_embedding(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    _create_track(client, cam_id, track_id=1)
    _create_track(client, cam_id, track_id=2)
    vec_a = [1.0] + [0.0] * 511
    vec_b = [0.0, 1.0] + [0.0] * 510

    first = client.post(
        "/api/v1/ingest/reid",
        headers=WORKER,
        json={"camera_id": cam_id, "track_id": 1, "embedding": vec_a},
    )
    second = client.post(
        "/api/v1/ingest/reid",
        headers=WORKER,
        json={"camera_id": cam_id, "track_id": 2, "embedding": vec_b},
    )

    assert first.json()["identity_id"] != second.json()["identity_id"]


def test_ingest_reid_404_when_track_missing(client, admin_token):
    cam_id = _create_camera(client, admin_token)

    resp = client.post(
        "/api/v1/ingest/reid",
        headers=WORKER,
        json={"camera_id": cam_id, "track_id": 999, "embedding": EMBEDDING},
    )

    assert resp.status_code == 404


def test_ingest_reid_rejects_short_embedding(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    _create_track(client, cam_id)

    resp = client.post(
        "/api/v1/ingest/reid",
        headers=WORKER,
        json={"camera_id": cam_id, "track_id": 1, "embedding": [0.1] * 256},
    )

    assert resp.status_code == 422


def test_ingest_reid_rejects_long_embedding(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    _create_track(client, cam_id)

    resp = client.post(
        "/api/v1/ingest/reid",
        headers=WORKER,
        json={"camera_id": cam_id, "track_id": 1, "embedding": [0.1] * 1024},
    )

    assert resp.status_code == 422


def test_ingest_reid_requires_worker_key(client, admin_token):
    cam_id = _create_camera(client, admin_token)
    _create_track(client, cam_id)

    resp = client.post(
        "/api/v1/ingest/reid",
        json={"camera_id": cam_id, "track_id": 1, "embedding": EMBEDDING},
    )

    assert resp.status_code == 401
