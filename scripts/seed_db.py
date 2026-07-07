"""Idempotent seed: first admin user + demo camera pointing at the sample video."""

import logging

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.core.database import SessionLocal
from backend.app.core.security import hash_password
from backend.app.models import Camera, CameraType, Role, User, Zone, ZoneType

logging.basicConfig(level="INFO")
log = logging.getLogger("seed")


def main() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == settings.first_admin_email)) is None:
            db.add(
                User(
                    email=settings.first_admin_email,
                    full_name="Admin",
                    role=Role.admin,
                    hashed_password=hash_password(settings.first_admin_password),
                )
            )
            log.info("created admin %s", settings.first_admin_email)

        if db.scalar(select(Camera).where(Camera.name == "demo-entrance")) is None:
            cam = Camera(
                name="demo-entrance",
                source="datasets/samples/retail_demo.mp4",
                type=CameraType.file,
                location="Store entrance (sample video)",
                fps_target=5,
            )
            db.add(cam)
            db.flush()
            db.add_all(
                [
                    Zone(
                        camera_id=cam.id,
                        name="entrance",
                        type=ZoneType.entrance,
                        polygon=[[0.0, 0.6], [0.35, 0.6], [0.35, 1.0], [0.0, 1.0]],
                    ),
                    Zone(
                        camera_id=cam.id,
                        name="checkout-queue",
                        type=ZoneType.queue,
                        polygon=[[0.55, 0.35], [0.98, 0.35], [0.98, 0.95], [0.55, 0.95]],
                    ),
                    Zone(
                        camera_id=cam.id,
                        name="aisle-A",
                        type=ZoneType.aisle,
                        polygon=[[0.3, 0.1], [0.6, 0.1], [0.6, 0.5], [0.3, 0.5]],
                    ),
                ]
            )
            log.info("created demo camera + zones")
        db.commit()
    log.info("seed complete")


if __name__ == "__main__":
    main()
