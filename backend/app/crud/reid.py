"""Re-ID data layer: identities gallery + track embedding storage/linking.

No matching *decisions* here (see backend/app/services/reid_matcher.py for
the cosine-similarity logic) - this module only stores, links, and queries.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.detection import Track
from backend.app.models.reid import Identity


def store_track_embedding(
    db: Session, camera_id: int, track_id: int, embedding: list[float]
) -> Track | None:
    """Attach an embedding to an already-ingested track. None if the track
    doesn't exist yet - the worker must call /ingest/track first."""
    track = db.scalar(select(Track).where(Track.camera_id == camera_id, Track.track_id == track_id))
    if track is None:
        return None
    track.embedding = embedding
    db.commit()
    db.refresh(track)
    return track


def create_identity(db: Session, embedding: list[float], seen_at: datetime) -> Identity:
    identity = Identity(embedding=embedding, first_seen=seen_at, last_seen=seen_at, track_count=1)
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity


def create_identity_from_track(db: Session, track: Track, embedding: list[float]) -> Identity:
    """New gallery entry seeded by one track - the matcher's no-match branch.
    Unlike link_track_to_identity, track_count is not incremented here: it
    already starts at 1 in create_identity, correctly counting this track."""
    identity = create_identity(db, embedding, track.last_seen)
    track.identity_id = identity.id
    db.commit()
    db.refresh(track)
    db.refresh(identity)
    return identity


def get_identity(db: Session, identity_id: int) -> Identity | None:
    return db.get(Identity, identity_id)


def link_track_to_identity(db: Session, track: Track, identity: Identity) -> Track:
    track.identity_id = identity.id
    identity.last_seen = max(identity.last_seen, track.last_seen)
    identity.track_count += 1
    db.commit()
    db.refresh(track)
    return track


def get_identity_journey(db: Session, identity_id: int) -> list[Track]:
    """All tracks linked to this identity, ordered by when they were seen -
    the cross-camera path. Backs GET /reid/identities/{id}/journey."""
    return list(
        db.scalars(select(Track).where(Track.identity_id == identity_id).order_by(Track.first_seen))
    )


def list_recent_identities(
    db: Session, min_track_count: int = 2, limit: int = 50
) -> list[Identity]:
    """Identities linked to more than one track, most recently seen first -
    "matched more than once" is the plain-language definition of a
    re-identification (same-camera or cross-camera). Backs
    GET /reid/identities."""
    return list(
        db.scalars(
            select(Identity)
            .where(Identity.track_count >= min_track_count)
            .order_by(Identity.last_seen.desc())
            .limit(limit)
        )
    )
