from datetime import UTC, datetime, timedelta

from backend.app.crud import reid as crud
from backend.app.models import Camera, CameraType, Track

EMBEDDING = [0.1] * 512


def _naive(dt: datetime) -> datetime:
    """SQLite drops tzinfo on DateTime(timezone=True) round-trips (Postgres
    doesn't) - strip it on both sides so these tests aren't SQLite-specific."""
    return dt.replace(tzinfo=None)


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
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def test_store_track_embedding_attaches_vector(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    _make_track(db_session, cam.id, 1, now - timedelta(minutes=1), now)

    track = crud.store_track_embedding(db_session, cam.id, 1, EMBEDDING)

    assert track is not None
    assert track.embedding == EMBEDDING


def test_store_track_embedding_returns_none_for_missing_track(db_session):
    result = crud.store_track_embedding(db_session, 999, 1, EMBEDDING)
    assert result is None


def test_create_and_get_identity(db_session):
    now = datetime.now(UTC)

    identity = crud.create_identity(db_session, EMBEDDING, now)

    assert identity.id is not None
    assert identity.track_count == 1
    assert _naive(identity.first_seen) == _naive(now)
    assert _naive(identity.last_seen) == _naive(now)
    fetched = crud.get_identity(db_session, identity.id)
    assert fetched is not None
    assert fetched.id == identity.id


def test_get_identity_returns_none_for_missing_id(db_session):
    assert crud.get_identity(db_session, 999) is None


def test_link_track_to_identity_updates_gallery(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    track = _make_track(db_session, cam.id, 1, now - timedelta(minutes=1), now)
    identity = crud.create_identity(db_session, EMBEDDING, now - timedelta(hours=1))

    updated = crud.link_track_to_identity(db_session, track, identity)

    assert updated.identity_id == identity.id
    assert identity.track_count == 2
    assert _naive(identity.last_seen) == _naive(now)


def test_link_track_to_identity_keeps_latest_last_seen(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    earlier_track = _make_track(
        db_session, cam.id, 1, now - timedelta(hours=2), now - timedelta(hours=1)
    )
    identity = crud.create_identity(db_session, EMBEDDING, now)

    crud.link_track_to_identity(db_session, earlier_track, identity)

    # linking an older track must not move last_seen backwards
    assert _naive(identity.last_seen) == _naive(now)


def test_get_identity_journey_orders_by_first_seen_across_cameras(db_session):
    cam_a = _make_camera(db_session, name="cam-a")
    cam_b = _make_camera(db_session, name="cam-b")
    now = datetime.now(UTC)
    identity = crud.create_identity(db_session, EMBEDDING, now)
    later_track = _make_track(db_session, cam_b.id, 1, now, now + timedelta(minutes=5))
    earlier_track = _make_track(
        db_session, cam_a.id, 1, now - timedelta(minutes=10), now - timedelta(minutes=5)
    )
    crud.link_track_to_identity(db_session, later_track, identity)
    crud.link_track_to_identity(db_session, earlier_track, identity)

    journey = crud.get_identity_journey(db_session, identity.id)

    assert [t.id for t in journey] == [earlier_track.id, later_track.id]
    assert [t.camera_id for t in journey] == [cam_a.id, cam_b.id]


def test_get_identity_journey_empty_for_unmatched_identity(db_session):
    identity = crud.create_identity(db_session, EMBEDDING, datetime.now(UTC))
    assert crud.get_identity_journey(db_session, identity.id) == []
