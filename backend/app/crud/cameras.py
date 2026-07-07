from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.camera import Camera, Zone
from backend.app.schemas.camera import CameraCreate, CameraUpdate, ZoneCreate, ZoneUpdate


def list_cameras(db: Session, active_only: bool = False) -> list[Camera]:
    stmt = select(Camera).order_by(Camera.id)
    if active_only:
        stmt = stmt.where(Camera.is_active.is_(True))
    return list(db.scalars(stmt))


def get(db: Session, camera_id: int) -> Camera | None:
    return db.get(Camera, camera_id)


def create(db: Session, data: CameraCreate) -> Camera:
    cam = Camera(**data.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def update(db: Session, cam: Camera, data: CameraUpdate) -> Camera:
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cam, k, v)
    db.commit()
    db.refresh(cam)
    return cam


def delete(db: Session, cam: Camera) -> None:
    db.delete(cam)
    db.commit()


def add_zone(db: Session, cam: Camera, data: ZoneCreate) -> Zone:
    zone = Zone(camera_id=cam.id, **data.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


def update_zone(db: Session, zone: Zone, data: ZoneUpdate) -> Zone:
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(zone, k, v)
    db.commit()
    db.refresh(zone)
    return zone


def delete_zone(db: Session, zone: Zone) -> None:
    db.delete(zone)
    db.commit()
