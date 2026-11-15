"""evaluation tables

Revision ID: b3e1a7d40001
Revises: 221e157a59e6
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3e1a7d40001"
down_revision: Union[str, Sequence[str], None] = "221e157a59e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "dataset_samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("sample_ref", sa.String(100), nullable=False),
        sa.Column("split", sa.String(12), nullable=False),
        sa.Column("true_grade", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("split IN ('train', 'validation', 'test')", name="ck_dataset_samples_split"),
        sa.UniqueConstraint("dataset_id", "sample_ref", name="uq_dataset_samples_ref"),
    )
    op.create_index("ix_dataset_samples_dataset_id", "dataset_samples", ["dataset_id"])
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("kind", "version", name="uq_model_versions_kind_version"),
    )
    op.create_index(
        "uq_model_versions_one_active",
        "model_versions",
        ["kind"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_version_id", sa.Integer(), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("split", sa.String(12), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("split IN ('train', 'validation', 'test')", name="ck_evaluation_runs_split"),
        sa.CheckConstraint("sample_count > 0", name="ck_evaluation_runs_sample_count"),
        sa.UniqueConstraint("model_version_id", "split", "run_at", name="uq_evaluation_runs_identity"),
    )
    op.create_index("ix_evaluation_runs_model_version_id", "evaluation_runs", ["model_version_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_model_version_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("uq_model_versions_one_active", table_name="model_versions")
    op.drop_table("model_versions")
    op.drop_index("ix_dataset_samples_dataset_id", table_name="dataset_samples")
    op.drop_table("dataset_samples")
    op.drop_table("datasets")   