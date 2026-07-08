"""Cross-camera Re-ID read API. See docs/REID.md for the full design.

No write endpoints here - embeddings arrive via /ingest/reid (internal,
X-Worker-Key auth, see api/v1/ingest.py). This router is viewer+ read-only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import require_viewer
from backend.app.crud import reid as crud
from backend.app.schemas.reid import IdentityJourneyOut, IdentityOut

router = APIRouter(prefix="/reid", tags=["reid"], dependencies=[Depends(require_viewer)])


@router.get("/identities", response_model=list[IdentityOut])
def list_identities(
    db: Annotated[Session, Depends(get_db)],
    min_track_count: int = 2,
    limit: int = 50,
) -> list:
    """Recently re-identified visitors - identities matched more than once."""
    return crud.list_recent_identities(db, min_track_count=min_track_count, limit=limit)


@router.get("/identities/{identity_id}/journey", response_model=IdentityJourneyOut)
def get_journey(identity_id: int, db: Annotated[Session, Depends(get_db)]) -> dict:
    """One identity's cross-camera (or same-camera) path: every linked track,
    ordered by when it was seen."""
    identity = crud.get_identity(db, identity_id)
    if identity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Identity not found")
    tracks = crud.get_identity_journey(db, identity_id)
    return {"identity": identity, "tracks": tracks}
