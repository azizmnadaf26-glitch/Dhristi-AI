from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint("outcome IN ('success', 'denied', 'failure')", name="ck_audit_outcome"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    outcome: Mapped[str] = mapped_column(String(10))
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    object_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(200), nullable=True)