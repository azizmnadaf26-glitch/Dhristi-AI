from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DatasetSample(Base):
    __tablename__ = "dataset_samples"
    __table_args__ = (
        CheckConstraint("split IN ('train', 'validation', 'test')", name="ck_dataset_samples_split"),
        UniqueConstraint("dataset_id", "sample_ref", name="uq_dataset_samples_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True)
    sample_ref: Mapped[str] = mapped_column(String(100))
    split: Mapped[str] = mapped_column(String(12))
    true_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = unknown, 0 is real
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("kind", "version", name="uq_model_versions_kind_version"),
        Index(
            "uq_model_versions_one_active",
            "kind",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    version: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    notes: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        CheckConstraint("split IN ('train', 'validation', 'test')", name="ck_evaluation_runs_split"),
        CheckConstraint("sample_count > 0", name="ck_evaluation_runs_sample_count"),
        UniqueConstraint("model_version_id", "split", "run_at", name="uq_evaluation_runs_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"), index=True)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id"), nullable=True)
    split: Mapped[str] = mapped_column(String(12))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sample_count: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[dict] = mapped_column(JSON)  # supplied by the model team, never computed here
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)