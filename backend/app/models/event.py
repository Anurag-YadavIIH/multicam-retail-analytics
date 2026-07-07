"""Events, alerts, analytics snapshots, reports, audit logs."""

import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class EventType(str, enum.Enum):
    entry = "entry"
    exit = "exit"
    zone_enter = "zone_enter"
    zone_exit = "zone_exit"
    queue_join = "queue_join"
    queue_leave = "queue_leave"
    shelf_interaction = "shelf_interaction"
    loitering = "loitering"
    restricted_zone = "restricted_zone"


class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class AlertType(str, enum.Enum):
    high_queue = "high_queue"
    camera_offline = "camera_offline"
    crowding = "crowding"
    shelf_empty = "shelf_empty"
    loitering = "loitering"
    restricted_zone = "restricted_zone"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    type: Mapped[EventType] = mapped_column(Enum(EventType), index=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    type: Mapped[AlertType] = mapped_column(Enum(AlertType), index=True)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity))
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AnalyticsSnapshot(Base):
    """Per-camera aggregated metrics on a fixed interval (default 60s)."""

    __tablename__ = "analytics_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    people_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_visitors: Mapped[int] = mapped_column(Integer, default=0)
    avg_dwell_s: Mapped[float] = mapped_column(Float, default=0.0)
    queue_length: Mapped[int] = mapped_column(Integer, default=0)
    avg_wait_s: Mapped[float] = mapped_column(Float, default=0.0)
    zone_occupancy: Mapped[dict] = mapped_column(JSON, default=dict)
    fps: Mapped[float] = mapped_column(Float, default=0.0)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    kind: Mapped[str] = mapped_column(String(50))  # daily | heatmap | custom
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True
    )
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(120))
    resource: Mapped[str] = mapped_column(String(120))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
