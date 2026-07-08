"""Frames, detections, tracks - the vision write path."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Frame(Base):
    """Lightweight frame metadata. Raw JPEGs go to MinIO (object_key)."""

    __tablename__ = "frames"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    class_name: Mapped[str] = mapped_column(String(50), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    # bbox normalized xyxy
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    x2: Mapped[float] = mapped_column(Float)
    y2: Mapped[float] = mapped_column(Float)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class Track(Base):
    """One row per (camera, track_id) lifetime, updated as the track evolves."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    track_id: Mapped[int] = mapped_column(Integer, index=True)
    class_name: Mapped[str] = mapped_column(String(50), default="person")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    avg_speed_px_s: Mapped[float] = mapped_column(Float, default=0.0)
    # downsampled trajectory [[x, y, t_offset_s], ...] in normalized coords
    trajectory: Mapped[list] = mapped_column(JSON, default=list)
    zones_visited: Mapped[list] = mapped_column(JSON, default=list)
    # cross-camera re-id (see docs/REID.md) - both null until the worker posts
    # /ingest/reid and, later, the matcher links this track to a gallery identity
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    identity_id: Mapped[int | None] = mapped_column(
        ForeignKey("identities.id", ondelete="SET NULL"), nullable=True, index=True
    )
