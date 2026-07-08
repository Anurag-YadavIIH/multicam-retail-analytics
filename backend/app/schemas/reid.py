"""Re-ID schemas: worker ingest + the identities/journey read API.
See docs/REID.md for the full design."""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.schemas.common import ORMModel

REID_EMBEDDING_DIM = 512


class ReidIngestIn(BaseModel):
    """Posted by the vision worker once a closed track's embedding is ready.

    Requires /ingest/track to have already been called for this
    (camera_id, track_id) - see the ordering contract in docs/REID.md.
    """

    camera_id: int
    track_id: int
    embedding: list[float] = Field(min_length=REID_EMBEDDING_DIM, max_length=REID_EMBEDDING_DIM)


class IdentityOut(ORMModel):
    id: int
    first_seen: datetime
    last_seen: datetime
    track_count: int


class JourneyTrackOut(ORMModel):
    camera_id: int
    track_id: int
    first_seen: datetime
    last_seen: datetime
    trajectory: list
    zones_visited: list


class IdentityJourneyOut(BaseModel):
    identity: IdentityOut
    tracks: list[JourneyTrackOut]
