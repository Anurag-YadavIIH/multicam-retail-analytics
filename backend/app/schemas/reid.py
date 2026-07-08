"""Re-ID ingest schema. See docs/REID.md for the full design."""

from pydantic import BaseModel, Field

REID_EMBEDDING_DIM = 512


class ReidIngestIn(BaseModel):
    """Posted by the vision worker once a closed track's embedding is ready.

    Requires /ingest/track to have already been called for this
    (camera_id, track_id) - see the ordering contract in docs/REID.md.
    """

    camera_id: int
    track_id: int
    embedding: list[float] = Field(min_length=REID_EMBEDDING_DIM, max_length=REID_EMBEDDING_DIM)
