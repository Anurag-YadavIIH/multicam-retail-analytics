from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import require_viewer
from backend.app.models import Alert, AnalyticsSnapshot, Camera, CameraStatus, Track
from backend.app.schemas.analytics import OverviewOut, SnapshotOut, TrafficPoint

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_viewer)])


@router.get("/overview", response_model=OverviewOut)
def overview(db: Annotated[Session, Depends(get_db)]) -> OverviewOut:
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    visitors = (
        db.scalar(
            select(func.count(func.distinct(Track.track_id))).where(
                Track.first_seen >= day_start, Track.class_name == "person"
            )
        )
        or 0
    )
    latest = db.execute(
        select(AnalyticsSnapshot.camera_id, func.max(AnalyticsSnapshot.ts)).group_by(
            AnalyticsSnapshot.camera_id
        )
    ).all()
    occupancy = 0
    for camera_id, ts in latest:
        snap = db.scalar(
            select(AnalyticsSnapshot).where(
                AnalyticsSnapshot.camera_id == camera_id, AnalyticsSnapshot.ts == ts
            )
        )
        if snap:
            snap_ts = snap.ts if snap.ts.tzinfo else snap.ts.replace(tzinfo=UTC)
            if (now - snap_ts) < timedelta(minutes=5):
                occupancy += snap.people_count
    avg_dwell = (
        db.scalar(select(func.avg(Track.duration_s)).where(Track.first_seen >= day_start)) or 0.0
    )
    max_queue = (
        db.scalar(
            select(func.max(AnalyticsSnapshot.queue_length)).where(
                AnalyticsSnapshot.ts >= day_start
            )
        )
        or 0
    )
    active = (
        db.scalar(select(func.count(Camera.id)).where(Camera.status == CameraStatus.online)) or 0
    )
    open_alerts = db.scalar(select(func.count(Alert.id)).where(Alert.acknowledged.is_(False))) or 0
    return OverviewOut(
        total_visitors_today=visitors,
        current_occupancy=occupancy,
        avg_dwell_s=round(float(avg_dwell), 1),
        max_queue_length=max_queue,
        active_cameras=active,
        open_alerts=open_alerts,
    )


@router.get("/traffic", response_model=list[TrafficPoint])
def traffic(
    db: Annotated[Session, Depends(get_db)],
    camera_id: int | None = None,
    hours: int = Query(default=24, ge=1, le=24 * 7),
) -> list[TrafficPoint]:
    """Traffic trend: people_count sampled from snapshots."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    stmt = (
        select(AnalyticsSnapshot.ts, AnalyticsSnapshot.people_count)
        .where(AnalyticsSnapshot.ts >= since)
        .order_by(AnalyticsSnapshot.ts)
    )
    if camera_id is not None:
        stmt = stmt.where(AnalyticsSnapshot.camera_id == camera_id)
    return [TrafficPoint(ts=ts, count=c) for ts, c in db.execute(stmt).all()]


@router.get("/snapshots", response_model=list[SnapshotOut])
def snapshots(
    db: Annotated[Session, Depends(get_db)],
    camera_id: int,
    hours: int = Query(default=6, ge=1, le=168),
) -> list[AnalyticsSnapshot]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    return list(
        db.scalars(
            select(AnalyticsSnapshot)
            .where(AnalyticsSnapshot.camera_id == camera_id, AnalyticsSnapshot.ts >= since)
            .order_by(AnalyticsSnapshot.ts)
        )
    )


@router.get("/peak-hours")
def peak_hours(
    db: Annotated[Session, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=30),
) -> list[dict]:
    """Average occupancy per hour-of-day over the window."""
    since = datetime.now(UTC) - timedelta(days=days)
    rows = db.execute(
        select(
            func.extract("hour", AnalyticsSnapshot.ts).label("hour"),
            func.avg(AnalyticsSnapshot.people_count),
        )
        .where(AnalyticsSnapshot.ts >= since)
        .group_by("hour")
        .order_by("hour")
    ).all()
    return [{"hour": int(h), "avg_people": round(float(v or 0), 2)} for h, v in rows]


@router.get("/dwell")
def dwell(
    db: Annotated[Session, Depends(get_db)],
    camera_id: int | None = None,
    hours: int = Query(default=24, ge=1, le=168),
) -> dict:
    since = datetime.now(UTC) - timedelta(hours=hours)
    stmt = select(
        func.count(Track.id), func.avg(Track.duration_s), func.max(Track.duration_s)
    ).where(Track.first_seen >= since, Track.class_name == "person")
    if camera_id is not None:
        stmt = stmt.where(Track.camera_id == camera_id)
    count, avg_s, max_s = db.execute(stmt).one()
    return {
        "tracks": count or 0,
        "avg_dwell_s": round(float(avg_s or 0), 1),
        "max_dwell_s": round(float(max_s or 0), 1),
    }
