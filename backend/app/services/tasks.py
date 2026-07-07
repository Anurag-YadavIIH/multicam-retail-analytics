"""Celery tasks: health sweeps, daily reports, retention."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from backend.app.core.database import SessionLocal
from backend.app.models import (
    AnalyticsSnapshot,
    Camera,
    CameraStatus,
    Detection,
    Report,
)
from backend.app.models.event import AlertSeverity, AlertType
from backend.app.services.alert_service import raise_alert
from backend.app.services.celery_app import celery

OFFLINE_AFTER = timedelta(seconds=60)
DETECTION_RETENTION_DAYS = 7


@celery.task
def camera_health_sweep() -> int:
    """Mark cameras offline when heartbeats stop; raise alerts."""
    now = datetime.now(UTC)
    flagged = 0
    with SessionLocal() as db:
        cams = db.scalars(select(Camera).where(Camera.is_active.is_(True))).all()
        for cam in cams:
            stale = cam.last_heartbeat is None or (now - cam.last_heartbeat) > OFFLINE_AFTER
            if stale and cam.status == CameraStatus.online:
                cam.status = CameraStatus.offline
                raise_alert(
                    db,
                    AlertType.camera_offline,
                    AlertSeverity.critical,
                    f"Camera '{cam.name}' went offline",
                    cam.id,
                )
                flagged += 1
        db.commit()
    return flagged


@celery.task
def generate_daily_report() -> int:
    """Aggregate yesterday's snapshots into a Report row per camera."""
    now = datetime.now(UTC)
    start = now - timedelta(days=1)
    created = 0
    with SessionLocal() as db:
        rows = db.execute(
            select(
                AnalyticsSnapshot.camera_id,
                func.max(AnalyticsSnapshot.unique_visitors),
                func.avg(AnalyticsSnapshot.avg_dwell_s),
                func.max(AnalyticsSnapshot.queue_length),
            )
            .where(AnalyticsSnapshot.ts >= start)
            .group_by(AnalyticsSnapshot.camera_id)
        ).all()
        for camera_id, visitors, dwell, max_q in rows:
            db.add(
                Report(
                    kind="daily",
                    camera_id=camera_id,
                    summary={
                        "unique_visitors": int(visitors or 0),
                        "avg_dwell_s": round(float(dwell or 0), 1),
                        "max_queue_length": int(max_q or 0),
                        "window_start": start.isoformat(),
                        "window_end": now.isoformat(),
                    },
                )
            )
            created += 1
        db.commit()
    return created


@celery.task
def purge_old_detections() -> int:
    cutoff = datetime.now(UTC) - timedelta(days=DETECTION_RETENTION_DAYS)
    with SessionLocal() as db:
        result = db.execute(delete(Detection).where(Detection.ts < cutoff))
        db.commit()
        return result.rowcount or 0
