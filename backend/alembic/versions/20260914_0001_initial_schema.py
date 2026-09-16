"""Create initial application schema.

Revision ID: 20260914_0001
Revises:
Create Date: 2026-09-14 10:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260914_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_digests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("pdf_path", sa.String(length=1000), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "completed",
                "failed",
                name="digest_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_digests")),
        sa.UniqueConstraint("date", name=op.f("uq_daily_digests_date")),
    )
    op.create_index(op.f("ix_daily_digests_status"), "daily_digests", ["status"], unique=False)

    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_description", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_news_articles")),
        sa.UniqueConstraint("url", name=op.f("uq_news_articles_url")),
    )
    op.create_index(op.f("ix_news_articles_category"), "news_articles", ["category"], unique=False)
    op.create_index(
        op.f("ix_news_articles_published_at"), "news_articles", ["published_at"], unique=False
    )
    op.create_index(op.f("ix_news_articles_source"), "news_articles", ["source"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source_type",
            sa.Enum(
                "text",
                "forward",
                "voice",
                "webapp",
                name="task_source_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "inbox",
                "today",
                "week",
                "later",
                "done",
                name="task_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "importance",
            sa.Enum(
                "normal",
                "important",
                name="task_importance",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_due_at"), "tasks", ["due_at"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_telegram_user_id"), "tasks", ["telegram_user_id"], unique=False)

    op.create_table(
        "user_settings",
        sa.Column("telegram_user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("daily_digest_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("news_topics", sa.JSON(), nullable=False),
        sa.Column("news_max_articles", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("telegram_user_id", name=op.f("pk_user_settings")),
    )

    op.create_table(
        "digest_articles",
        sa.Column("digest_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["news_articles.id"],
            name=op.f("fk_digest_articles_article_id_news_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["digest_id"],
            ["daily_digests.id"],
            name=op.f("fk_digest_articles_digest_id_daily_digests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("digest_id", "article_id", name=op.f("pk_digest_articles")),
        sa.UniqueConstraint("digest_id", "position", name="uq_digest_position"),
    )


def downgrade() -> None:
    op.drop_table("digest_articles")
    op.drop_table("user_settings")
    op.drop_index(op.f("ix_tasks_telegram_user_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_due_at"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_news_articles_source"), table_name="news_articles")
    op.drop_index(op.f("ix_news_articles_published_at"), table_name="news_articles")
    op.drop_index(op.f("ix_news_articles_category"), table_name="news_articles")
    op.drop_table("news_articles")
    op.drop_index(op.f("ix_daily_digests_status"), table_name="daily_digests")
    op.drop_table("daily_digests")
