"""Add the daily digest delivery marker.

Revision ID: 20260914_0004
Revises: 20260914_0003
Create Date: 2026-09-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260914_0004"
down_revision: str | None = "20260914_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("last_daily_digest_sent_on", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "last_daily_digest_sent_on")
