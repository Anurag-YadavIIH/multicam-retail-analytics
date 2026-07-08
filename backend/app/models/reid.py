"""Cross-camera Re-ID: the global identity gallery. See docs/REID.md."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Identity(Base):
    """A global cross-camera identity - one row per known gallery entry."""

    __tablename__ = "identities"

    id: Mapped[int] = mapped_column(primary_key=True)
    embedding: Mapped[list] = mapped_column(JSON)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    track_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
