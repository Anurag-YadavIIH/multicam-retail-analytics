import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from redis import Redis
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import (
    require_manager,
    require_viewer,
    require_viewer_via_header_or_query,
)
from backend.app.core.redis_client import get_redis
from backend.app.core.security import STREAM_TOKEN_TTL_S, create_stream_token
from backend.app.crud import cameras as crud
from backend.app.models import AuditLog, Camera, CameraStatus, User, Zone
from backend.app.schemas.camera import (
    CameraCreate,
    CameraOut,
    CameraUpdate,
    StreamTokenOut,
    ZoneCreate,
    ZoneOut,
    ZoneUpdate,
)

router = APIRouter(prefix="/cameras", tags=["cameras"])

MJPEG_BOUNDARY = "frame"
STREAM_POLL_INTERVAL_S = 0.3


def _frame_key(camera_id: int) -> str:
    return f"frame:latest:{camera_id}"


def _mjpeg_parts(r: Redis, camera_id: int) -> Iterator[bytes]:
    key = _frame_key(camera_id)
    while True:
        data = r.get(key)
        if data:
            header = (
                f"--{MJPEG_BOUNDARY}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(data)}\r\n\r\n"
            )
            yield header.encode() + data + b"\r\n"
        time.sleep(STREAM_POLL_INTERVAL_S)


def _get_or_404(db: Session, camera_id: int) -> Camera:
    cam = crud.get(db, camera_id)
    if cam is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    return cam


@router.get("", response_model=list[CameraOut], dependencies=[Depends(require_viewer)])
def list_cameras(db: Annotated[Session, Depends(get_db)]) -> list[Camera]:
    return crud.list_cameras(db)


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(
    data: CameraCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> Camera:
    cam = crud.create(db, data)
    db.add(AuditLog(user_id=user.id, action="create", resource="camera", detail={"id": cam.id}))
    db.commit()
    return cam


@router.get("/{camera_id}", response_model=CameraOut, dependencies=[Depends(require_viewer)])
def get_camera(camera_id: int, db: Annotated[Session, Depends(get_db)]) -> Camera:
    return _get_or_404(db, camera_id)


@router.post(
    "/{camera_id}/stream-token",
    response_model=StreamTokenOut,
    dependencies=[Depends(require_viewer)],
)
def issue_stream_token(camera_id: int, db: Annotated[Session, Depends(get_db)]) -> StreamTokenOut:
    """Mint a ~60s camera-scoped token for the /snapshot and /stream ?token=
    query param, so a normal (much longer-lived) access token never has to sit
    in a URL. Requires a real JWT via the Authorization header to call."""
    _get_or_404(db, camera_id)
    return StreamTokenOut(token=create_stream_token(camera_id), expires_in=STREAM_TOKEN_TTL_S)


@router.get("/{camera_id}/snapshot", dependencies=[Depends(require_viewer_via_header_or_query)])
def snapshot_camera(
    camera_id: int,
    db: Annotated[Session, Depends(get_db)],
    r: Annotated[Redis, Depends(get_redis)],
) -> Response:
    """Single latest annotated JPEG - also the frame the zone editor draws over."""
    _get_or_404(db, camera_id)
    data = r.get(_frame_key(camera_id))
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No frame available yet")
    return Response(content=data, media_type="image/jpeg")


@router.get("/{camera_id}/stream", dependencies=[Depends(require_viewer_via_header_or_query)])
def stream_camera(
    camera_id: int,
    db: Annotated[Session, Depends(get_db)],
    r: Annotated[Redis, Depends(get_redis)],
) -> StreamingResponse:
    """MJPEG live preview, polling the Redis frame cache the vision worker fills."""
    _get_or_404(db, camera_id)
    return StreamingResponse(
        _mjpeg_parts(r, camera_id),
        media_type=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
    )


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    data: CameraUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> Camera:
    cam = _get_or_404(db, camera_id)
    updated = crud.update(db, cam, data)
    db.add(AuditLog(user_id=user.id, action="update", resource="camera", detail={"id": cam.id}))
    db.commit()
    return updated


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(
    camera_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> None:
    cam = _get_or_404(db, camera_id)
    crud.delete(db, cam)
    db.add(AuditLog(user_id=user.id, action="delete", resource="camera", detail={"id": camera_id}))
    db.commit()


@router.post("/{camera_id}/heartbeat", include_in_schema=False)
def heartbeat(camera_id: int, fps: float, db: Annotated[Session, Depends(get_db)]) -> dict:
    """Internal endpoint used by vision workers."""
    cam = _get_or_404(db, camera_id)
    cam.last_heartbeat = datetime.now(UTC)
    cam.measured_fps = fps
    cam.status = CameraStatus.online
    db.commit()
    return {"ok": True}


@router.post("/{camera_id}/zones", response_model=ZoneOut, status_code=status.HTTP_201_CREATED)
def add_zone(
    camera_id: int,
    data: ZoneCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> Zone:
    cam = _get_or_404(db, camera_id)
    return crud.add_zone(db, cam, data)


def _get_zone_or_404(db: Session, camera_id: int, zone_id: int) -> Zone:
    zone = db.get(Zone, zone_id)
    if zone is None or zone.camera_id != camera_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")
    return zone


@router.patch("/{camera_id}/zones/{zone_id}", response_model=ZoneOut)
def update_zone(
    camera_id: int,
    zone_id: int,
    data: ZoneUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> Zone:
    zone = _get_zone_or_404(db, camera_id, zone_id)
    return crud.update_zone(db, zone, data)


@router.delete("/{camera_id}/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(
    camera_id: int,
    zone_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_manager)],
) -> None:
    zone = _get_zone_or_404(db, camera_id, zone_id)
    crud.delete_zone(db, zone)
