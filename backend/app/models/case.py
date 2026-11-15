from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded','needs_recapture','graded','in_review','reviewed')",
            name="ck_cases_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    patient_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    eye: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded", index=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    filename: Mapped[str] = mapped_column(String(100))  # random name, never the user's
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    source_image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QualityResult(Base):
    __tablename__ = "quality_results"
    __table_args__ = (
        CheckConstraint("verdict IN ('usable','unusable')", name="ck_quality_verdict"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"))
    verdict: Mapped[str] = mapped_column(String(10))
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    engine_mode: Mapped[str] = mapped_column(String(20))
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (CheckConstraint("grade BETWEEN 0 AND 4", name="ck_prediction_grade"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"))
    grade: Mapped[int] = mapped_column(Integer)
    class_scores: Mapped[list] = mapped_column(JSON)
    model_score: Mapped[float] = mapped_column(Float)
    referable: Mapped[bool] = mapped_column(Boolean)
    low_confidence: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('confirm','override','recapture','refer')",
            name="ck_review_decision",
        ),
        CheckConstraint(
            "final_grade IS NULL OR final_grade BETWEEN 0 AND 4",
            name="ck_review_grade",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))
    final_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)