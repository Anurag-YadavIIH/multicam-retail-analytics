"""Re-ID data layer: identities gallery + track embedding storage/linking.

No matching logic here (see docs/REID.md - that's session 3). This module
only stores and queries; `link_track_to_identity` and `get_identity_journey`
aren't called by any route yet, but they're the primitives the future
matcher and journeys endpoint will use.
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
    the cross-camera path. Backs the future GET .../journey endpoint."""
    return list(
        db.scalars(select(Track).where(Track.identity_id == identity_id).order_by(Track.first_seen))
    )
