"""Camera and zone models."""

import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class CameraType(str, enum.Enum):
    rtsp = "rtsp"
    usb = "usb"
    file = "file"


class CameraStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    error = "error"
    disabled = "disabled"


class ZoneType(str, enum.Enum):
    entrance = "entrance"
    exit = "exit"
    aisle = "aisle"
    shelf = "shelf"
    queue = "queue"
    checkout = "checkout"
    restricted = "restricted"


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    source: Mapped[str] = mapped_column(String(500))  # rtsp url | device index | file path
    type: Mapped[CameraType] = mapped_column(Enum(CameraType), default=CameraType.rtsp)
    status: Mapped[CameraStatus] = mapped_column(Enum(CameraStatus), default=CameraStatus.offline)
    location: Mapped[str] = mapped_column(String(255), default="")
    fps_target: Mapped[int] = mapped_column(Integer, default=5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    measured_fps: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    zones: Mapped[list["Zone"]] = relationship(
        back_populates="camera", cascade="all, delete-orphan"
    )


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[ZoneType] = mapped_column(Enum(ZoneType), default=ZoneType.aisle)
    # polygon in normalized [0..1] coords: [[x, y], ...]
    polygon: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    camera: Mapped[Camera] = relationship(back_populates="zones")
