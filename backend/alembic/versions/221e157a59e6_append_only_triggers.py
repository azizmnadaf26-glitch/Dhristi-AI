"""append only triggers

Revision ID: 221e157a59e6
Revises: 88abe2684b89
Create Date: 2026-10-30 13:02:17.720822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '221e157a59e6'
down_revision: Union[str, Sequence[str], None] = '1a900d845e2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("audit_log", "reviews"):
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER {table}_no_{operation.lower()} "
                f"BEFORE {operation} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
            )


def downgrade() -> None:
    for table in ("audit_log", "reviews"):
        for operation in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS {table}_no_{operation}")