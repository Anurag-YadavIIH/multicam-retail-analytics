from datetime import UTC, datetime, timedelta

from backend.app.crud import reid as crud
from backend.app.models import Camera, CameraType, Track
from tests.conftest import auth

EMBEDDING = [0.1] * 512


def _make_camera(db, name: str = "cam") -> Camera:
    cam = Camera(name=name, source="0", type=CameraType.usb)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def _make_track(db, camera_id: int, track_id: int, first_seen, last_seen) -> Track:
    track = Track(
        camera_id=camera_id,
        track_id=track_id,
        class_name="person",
        first_seen=first_seen,
        last_seen=last_seen,
        trajectory=[[0.1, 0.2, 0.0]],
        zones_visited=["entrance"],
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def test_list_identities_excludes_singletons(client, admin_token, db_session):
    now = datetime.now(UTC)
    crud.create_identity(db_session, EMBEDDING, now)  # track_count=1, never matched again

    resp = client.get("/api/v1/reid/identities", headers=auth(admin_token))

    assert resp.status_code == 200
    assert resp.json() == []


def test_list_identities_returns_matched_ones_most_recent_first(client, admin_token, db_session):
    now = datetime.now(UTC)
    cam = _make_camera(db_session)

    older = crud.create_identity(db_session, EMBEDDING, now - timedelta(hours=2))
    t1 = _make_track(db_session, cam.id, 1, now - timedelta(hours=2), now - timedelta(hours=2))
    crud.link_track_to_identity(db_session, t1, older)

    newer = crud.create_identity(db_session, EMBEDDING, now - timedelta(minutes=10))
    t2 = _make_track(
        db_session, cam.id, 2, now - timedelta(minutes=10), now - timedelta(minutes=10)
    )
    crud.link_track_to_identity(db_session, t2, newer)

    resp = client.get("/api/v1/reid/identities", headers=auth(admin_token))

    assert resp.status_code == 200
    body = resp.json()
    assert [i["id"] for i in body] == [newer.id, older.id]
    assert all(i["track_count"] == 2 for i in body)


def test_list_identities_respects_min_track_count_and_limit(client, admin_token, db_session):
    now = datetime.now(UTC)
    cam = _make_camera(db_session)
    identity = crud.create_identity(db_session, EMBEDDING, now)
    for track_id in (1, 2, 3):
        t = _make_track(db_session, cam.id, track_id, now, now)
        crud.link_track_to_identity(db_session, t, identity)
    assert identity.track_count == 4

    resp = client.get(
        "/api/v1/reid/identities?min_track_count=4&limit=1", headers=auth(admin_token)
    )

    assert resp.status_code == 200
    assert [i["id"] for i in resp.json()] == [identity.id]


def test_list_identities_requires_auth(client):
    resp = client.get("/api/v1/reid/identities")
    assert resp.status_code == 401


def test_list_identities_viewer_allowed(client, viewer_token):
    resp = client.get("/api/v1/reid/identities", headers=auth(viewer_token))
    assert resp.status_code == 200


def test_get_journey_404_for_missing_identity(client, admin_token):
    resp = client.get("/api/v1/reid/identities/9999/journey", headers=auth(admin_token))
    assert resp.status_code == 404


def test_get_journey_orders_tracks_across_cameras(client, admin_token, db_session):
    now = datetime.now(UTC)
    cam_a = _make_camera(db_session, name="cam-a")
    cam_b = _make_camera(db_session, name="cam-b")
    identity = crud.create_identity(db_session, EMBEDDING, now)

    later = _make_track(db_session, cam_b.id, 1, now, now + timedelta(minutes=5))
    earlier = _make_track(
        db_session, cam_a.id, 1, now - timedelta(minutes=10), now - timedelta(minutes=5)
    )
    crud.link_track_to_identity(db_session, later, identity)
    crud.link_track_to_identity(db_session, earlier, identity)

    resp = client.get(f"/api/v1/reid/identities/{identity.id}/journey", headers=auth(admin_token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["identity"]["id"] == identity.id
    assert [t["camera_id"] for t in body["tracks"]] == [cam_a.id, cam_b.id]
    assert body["tracks"][0]["zones_visited"] == ["entrance"]


def test_get_journey_requires_auth(client, admin_token, db_session):
    identity = crud.create_identity(db_session, EMBEDDING, datetime.now(UTC))
    resp = client.get(f"/api/v1/reid/identities/{identity.id}/journey")
    assert resp.status_code == 401
