"""Internal ingestion endpoint: vision workers POST processed-frame results here.

Kept as HTTP (rather than direct DB writes from the worker) so the backend
remains the single writer, alerts/websockets stay consistent, and workers can
run on edge devices with only outbound HTTP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.crud import reid as reid_crud
from backend.app.models import AnalyticsSnapshot, Detection, Track
from backend.app.schemas.analytics import IngestDetection
from backend.app.schemas.reid import ReidIngestIn
from backend.app.services import metrics
from backend.app.services.alert_service import evaluate_snapshot
from backend.app.services.reid_matcher import match_or_create_identity
from backend.app.services.ws_manager import ws_manager

router = APIRouter(prefix="/ingest", tags=["internal"], include_in_schema=False)


def verify_worker(x_worker_key: Annotated[str | None, Header()] = None) -> None:
    # Workers authenticate with the app secret; rotate via env.
    if x_worker_key != get_settings().secret_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid worker key")


@router.post("/frame", dependencies=[Depends(verify_worker)])
async def ingest_frame(body: IngestDetection, db: Annotated[Session, Depends(get_db)]) -> dict:
    metrics.INGESTED_FRAMES.labels(camera_id=str(body.camera_id)).inc()
    metrics.CAMERA_FPS.labels(camera_id=str(body.camera_id)).set(body.fps)

    for d in body.detections:
        bbox = d["bbox"]
        db.add(
            Detection(
                camera_id=body.camera_id,
                ts=body.ts,
                class_name=d["class_name"],
                confidence=d["confidence"],
                x1=bbox[0],
                y1=bbox[1],
                x2=bbox[2],
                y2=bbox[3],
                track_id=d.get("track_id"),
            )
        )
        metrics.DETECTIONS_TOTAL.labels(
            camera_id=str(body.camera_id), class_name=d["class_name"]
        ).inc()

    if body.snapshot:
        s = body.snapshot
        db.add(
            AnalyticsSnapshot(
                camera_id=body.camera_id,
                ts=body.ts,
                people_count=s.get("people_count", 0),
                unique_visitors=s.get("unique_visitors", 0),
                avg_dwell_s=s.get("avg_dwell_s", 0.0),
                queue_length=s.get("queue_length", 0),
                avg_wait_s=s.get("avg_wait_s", 0.0),
                zone_occupancy=s.get("zone_occupancy", {}),
                fps=body.fps,
            )
        )
        metrics.QUEUE_LENGTH.labels(camera_id=str(body.camera_id)).set(s.get("queue_length", 0))
        metrics.PEOPLE_COUNT.labels(camera_id=str(body.camera_id)).set(s.get("people_count", 0))

    db.commit()

    created_alerts = []
    if body.snapshot:
        created_alerts = evaluate_snapshot(db, body.camera_id, body.snapshot)
        for a in created_alerts:
            metrics.ALERTS_TOTAL.labels(type=a.type.value, severity=a.severity.value).inc()
            await ws_manager.broadcast(
                "alerts",
                {
                    "id": a.id,
                    "type": a.type.value,
                    "severity": a.severity.value,
                    "message": a.message,
                    "camera_id": a.camera_id,
                    "ts": a.ts,
                },
            )

    await ws_manager.broadcast(
        f"detections:{body.camera_id}",
        {
            "camera_id": body.camera_id,
            "ts": body.ts,
            "fps": body.fps,
            "detections": body.detections,
        },
    )
    if body.snapshot:
        await ws_manager.broadcast(
            "analytics",
            {
                "camera_id": body.camera_id,
                "ts": body.ts,
                **body.snapshot,
            },
        )
    return {"ok": True, "alerts": len(created_alerts)}


@router.post("/track", dependencies=[Depends(verify_worker)])
def ingest_track(body: dict, db: Annotated[Session, Depends(get_db)]) -> dict:
    """Upsert a finished/updated track (called by worker on track close/refresh)."""
    from datetime import datetime as _dt

    def _parse(v):
        return _dt.fromisoformat(v) if isinstance(v, str) else v

    row = db.scalar(
        select(Track).where(
            Track.camera_id == body["camera_id"], Track.track_id == body["track_id"]
        )
    )
    if row is None:
        row = Track(camera_id=body["camera_id"], track_id=body["track_id"])
        db.add(row)
    row.class_name = body.get("class_name", "person")
    row.first_seen = _parse(body["first_seen"])
    row.last_seen = _parse(body["last_seen"])
    row.duration_s = body.get("duration_s", 0.0)
    row.avg_speed_px_s = body.get("avg_speed_px_s", 0.0)
    row.trajectory = body.get("trajectory", [])
    row.zones_visited = body.get("zones_visited", [])
    db.commit()
    return {"ok": True}


@router.post("/reid", dependencies=[Depends(verify_worker)])
def ingest_reid(body: ReidIngestIn, db: Annotated[Session, Depends(get_db)]) -> dict:
    """Store a closed track's Re-ID embedding and match it against the active
    gallery inline (see docs/REID.md - this is the lite-mode transport path;
    a full-profile deployment can additionally fan this out via Kafka to the
    same matcher function). Requires /ingest/track to have already been
    called for this camera_id/track_id - 404 otherwise, so the worker knows
    to retry rather than silently drop it."""
    track = reid_crud.store_track_embedding(db, body.camera_id, body.track_id, body.embedding)
    if track is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Track not found - send /ingest/track first")
    identity = match_or_create_identity(db, track, body.embedding)
    return {"ok": True, "identity_id": identity.id}
