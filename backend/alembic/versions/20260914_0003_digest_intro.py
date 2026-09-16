"""Add stored digest introduction.

Revision ID: 20260914_0003
Revises: 20260914_0002
Create Date: 2026-09-14 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260914_0003"
down_revision: str | None = "20260914_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("daily_digests", sa.Column("intro", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("daily_digests", "intro")
