"""Re-ID matching: cosine similarity against the active gallery.

Pure business logic - takes a db session, a track, and its embedding; has no
knowledge of Kafka, Redis, or HTTP transport (see docs/REID.md "Matching").
Lives backend-side (not in analytics/) because it needs the ORM/DB session,
which would break analytics/'s framework-free, worker-importable invariant.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.crud import reid as crud
from backend.app.models.detection import Track
from backend.app.models.reid import Identity


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def active_gallery(db: Session, ttl_hours: float, now: datetime) -> list[Identity]:
    """Identities seen within the TTL window - the only ones eligible to
    match against. Older identities are kept (history/audit) but excluded."""
    cutoff = now - timedelta(hours=ttl_hours)
    return list(db.scalars(select(Identity).where(Identity.last_seen > cutoff)))


def match_or_create_identity(
    db: Session,
    track: Track,
    embedding: list[float],
    *,
    ttl_hours: float | None = None,
    threshold: float | None = None,
) -> Identity:
    """Best cosine match above `threshold` among identities active within
    `ttl_hours` -> link `track` to it. No qualifying match -> a new identity
    seeded from this track's embedding. Defaults come from Settings
    (reid_gallery_ttl_hours / reid_match_threshold) when not overridden."""
    settings = get_settings()
    ttl_hours = settings.reid_gallery_ttl_hours if ttl_hours is None else ttl_hours
    threshold = settings.reid_match_threshold if threshold is None else threshold

    gallery = active_gallery(db, ttl_hours, track.last_seen)
    best_identity: Identity | None = None
    best_score = threshold
    for identity in gallery:
        score = cosine_similarity(embedding, identity.embedding)
        if score >= best_score:
            best_identity, best_score = identity, score

    if best_identity is not None:
        crud.link_track_to_identity(db, track, best_identity)  # returns the track, not the identity
        return best_identity
    return crud.create_identity_from_track(db, track, embedding)
