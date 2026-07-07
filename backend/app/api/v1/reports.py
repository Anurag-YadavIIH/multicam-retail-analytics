from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import require_viewer
from backend.app.models import Report

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_viewer)])


@router.get("")
def list_reports(
    db: Annotated[Session, Depends(get_db)],
    kind: str | None = None,
    limit: int = Query(default=50, le=200),
) -> list[dict]:
    stmt = select(Report).order_by(Report.created_at.desc()).limit(limit)
    if kind:
        stmt = stmt.where(Report.kind == kind)
    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "kind": r.kind,
            "camera_id": r.camera_id,
            "summary": r.summary,
            "object_key": r.object_key,
        }
        for r in db.scalars(stmt)
    ]
