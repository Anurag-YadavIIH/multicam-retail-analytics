from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import require_manager, require_viewer
from backend.app.models import Alert
from backend.app.schemas.analytics import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut], dependencies=[Depends(require_viewer)])
def list_alerts(
    db: Annotated[Session, Depends(get_db)],
    hours: int = Query(default=24, ge=1, le=24 * 30),
    unacknowledged_only: bool = False,
    limit: int = Query(default=100, le=500),
) -> list[Alert]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    stmt = select(Alert).where(Alert.ts >= since).order_by(Alert.ts.desc()).limit(limit)
    if unacknowledged_only:
        stmt = stmt.where(Alert.acknowledged.is_(False))
    return list(db.scalars(stmt))


@router.post("/{alert_id}/ack", response_model=AlertOut, dependencies=[Depends(require_manager)])
def acknowledge(alert_id: int, db: Annotated[Session, Depends(get_db)]) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    alert.acknowledged = True
    db.commit()
    db.refresh(alert)
    return alert
