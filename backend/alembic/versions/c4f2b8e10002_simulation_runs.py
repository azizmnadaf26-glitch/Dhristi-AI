"""simulation runs

Revision ID: c4f2b8e10002
Revises: b3e1a7d40001
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4f2b8e10002"
down_revision: Union[str, Sequence[str], None] = "b3e1a7d40001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("engine_mode", sa.String(20), nullable=True),
        sa.Column("error_message", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_simulation_runs_status",
        ),
    )
    op.create_index("ix_simulation_runs_created_by", "simulation_runs", ["created_by"])
    op.create_index("ix_simulation_runs_status", "simulation_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_status", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_created_by", table_name="simulation_runs")
    op.drop_table("simulation_runs")