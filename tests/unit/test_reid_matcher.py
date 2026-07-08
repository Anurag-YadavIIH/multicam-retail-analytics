from datetime import UTC, datetime, timedelta

from backend.app.crud import reid as crud
from backend.app.models import Camera, CameraType, Track
from backend.app.services.reid_matcher import (
    active_gallery,
    cosine_similarity,
    match_or_create_identity,
)

DIM = 512
TTL_HOURS = 24.0
THRESHOLD = 0.65


def _vec(index: int) -> list[float]:
    """A unit vector along one axis - orthogonal to _vec(j) for j != index."""
    v = [0.0] * DIM
    v[index] = 1.0
    return v


def _make_camera(db, name: str = "cam") -> Camera:
    cam = Camera(name=name, source="0", type=CameraType.usb)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def _make_track(db, camera_id: int, track_id: int, seen_at: datetime) -> Track:
    track = Track(
        camera_id=camera_id,
        track_id=track_id,
        class_name="person",
        first_seen=seen_at - timedelta(seconds=5),
        last_seen=seen_at,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def test_cosine_similarity_identical_vectors_is_one():
    v = _vec(0)
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert abs(cosine_similarity(_vec(0), _vec(1))) < 1e-9


def test_cosine_similarity_zero_vector_is_zero():
    zero = [0.0] * DIM
    assert cosine_similarity(zero, _vec(0)) == 0.0


def test_active_gallery_excludes_stale_identities(db_session):
    now = datetime.now(UTC)
    crud.create_identity(db_session, _vec(0), now - timedelta(hours=1))
    crud.create_identity(db_session, _vec(1), now - timedelta(hours=48))

    gallery = active_gallery(db_session, ttl_hours=TTL_HOURS, now=now)

    assert len(gallery) == 1


def test_match_or_create_creates_identity_for_empty_gallery(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    track = _make_track(db_session, cam.id, 1, now)

    identity = match_or_create_identity(
        db_session, track, _vec(0), ttl_hours=TTL_HOURS, threshold=THRESHOLD
    )

    assert identity.id is not None
    assert identity.track_count == 1
    assert track.identity_id == identity.id


def test_match_or_create_links_close_match(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    existing = crud.create_identity(db_session, _vec(0), now - timedelta(minutes=30))
    track = _make_track(db_session, cam.id, 1, now)

    identity = match_or_create_identity(
        db_session, track, _vec(0), ttl_hours=TTL_HOURS, threshold=THRESHOLD
    )

    assert identity.id == existing.id
    assert identity.track_count == 2
    assert track.identity_id == existing.id


def test_match_or_create_below_threshold_creates_new(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    existing = crud.create_identity(db_session, _vec(0), now - timedelta(minutes=30))
    track = _make_track(db_session, cam.id, 1, now)

    identity = match_or_create_identity(
        db_session, track, _vec(1), ttl_hours=TTL_HOURS, threshold=THRESHOLD
    )

    assert identity.id != existing.id
    assert identity.track_count == 1
    assert existing.track_count == 1  # untouched


def test_match_or_create_excludes_stale_identity_even_if_identical_embedding(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    stale = crud.create_identity(db_session, _vec(0), now - timedelta(hours=48))
    track = _make_track(db_session, cam.id, 1, now)

    identity = match_or_create_identity(
        db_session, track, _vec(0), ttl_hours=TTL_HOURS, threshold=THRESHOLD
    )

    assert identity.id != stale.id
    assert identity.track_count == 1


def test_match_or_create_ttl_override_includes_older_identity(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    old = crud.create_identity(db_session, _vec(0), now - timedelta(hours=30))
    track = _make_track(db_session, cam.id, 1, now)

    identity = match_or_create_identity(
        db_session, track, _vec(0), ttl_hours=48, threshold=THRESHOLD
    )

    assert identity.id == old.id


def test_match_or_create_default_threshold_rejects_partial_match(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    existing = crud.create_identity(db_session, _vec(0), now - timedelta(minutes=5))
    partial = [0.5, 0.8660254037844386] + [0.0] * (DIM - 2)  # cosine 0.5 vs _vec(0)
    track = _make_track(db_session, cam.id, 1, now)

    identity = match_or_create_identity(
        db_session, track, partial, ttl_hours=TTL_HOURS, threshold=THRESHOLD
    )

    assert identity.id != existing.id  # 0.5 < 0.65


def test_match_or_create_lower_threshold_accepts_partial_match(db_session):
    cam = _make_camera(db_session)
    now = datetime.now(UTC)
    existing = crud.create_identity(db_session, _vec(0), now - timedelta(minutes=5))
    partial = [0.5, 0.8660254037844386] + [0.0] * (DIM - 2)  # cosine 0.5 vs _vec(0)
    track = _make_track(db_session, cam.id, 1, now)

    identity = match_or_create_identity(
        db_session, track, partial, ttl_hours=TTL_HOURS, threshold=0.4
    )

    assert identity.id == existing.id  # 0.5 >= 0.4
