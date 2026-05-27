"""search candidates cache

Revision ID: 20260530_0004
Revises: 20260529_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260530_0004"
down_revision: str | None = "20260529_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("query_hash", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("payload", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "query_hash", "source_kind", "source_id", name="search_candidates_unique_source"
        ),
    )
    op.create_index("idx_search_query_hash", "search_candidates", ["query_hash"])
    op.create_index("idx_search_created_at", "search_candidates", [sa.text("created_at DESC")])

    op.add_column(
        "tracks",
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("tracks", "metadata")
    op.drop_index("idx_search_created_at", table_name="search_candidates")
    op.drop_index("idx_search_query_hash", table_name="search_candidates")
    op.drop_table("search_candidates")
