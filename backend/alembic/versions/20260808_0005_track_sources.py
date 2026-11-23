"""track_sources index + acoustid_fingerprint

Revision ID: 20260808_0005
Revises: 20260530_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260808_0005"
down_revision: str | None = "20260530_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE track_status ADD VALUE IF NOT EXISTS 'unrecoverable'")

    op.add_column("tracks", sa.Column("acoustid_fingerprint", sa.Text(), nullable=True))

    op.create_table(
        "track_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("original_filename", sa.String(), nullable=True),
        sa.Column(
            "original_tags",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("added_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("recovery_priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_track_sources_track", "track_sources", ["track_id"])
    op.create_index(
        "idx_track_sources_kind_status",
        "track_sources",
        ["source_kind", "last_status"],
    )

    # Backfill denormalized tracks.source_* into track_sources.
    op.execute(
        """
        INSERT INTO track_sources (
            track_id, source_kind, source_url, source_id,
            added_by_user_id, recovery_priority, last_status
        )
        SELECT
            t.id,
            CASE
                WHEN t.source_kind = 'upload' THEN 'user_upload'
                WHEN t.source_kind IS NULL OR t.source_kind = '' THEN 'unknown'
                ELSE t.source_kind
            END,
            NULLIF(t.source_url, ''),
            t.source_id,
            t.added_by_user_id,
            CASE
                WHEN t.source_kind IN (
                    'soundcloud', 'bandcamp', 'archive_org', 'fma', 'jamendo'
                ) THEN 10
                WHEN t.source_kind IN ('upload', 'user_upload') THEN 60
                WHEN t.source_kind LIKE 'restricted:%' THEN 200
                ELSE 30
            END,
            CASE WHEN t.status = 'ready' THEN 'ok' ELSE NULL END
        FROM tracks t
        WHERE t.source_kind IS NOT NULL
           OR (t.source_url IS NOT NULL AND t.source_url <> '')
           OR t.source_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_track_sources_kind_status", table_name="track_sources")
    op.drop_index("idx_track_sources_track", table_name="track_sources")
    op.drop_table("track_sources")
    op.drop_column("tracks", "acoustid_fingerprint")
    # PostgreSQL cannot easily remove enum values; leave 'unrecoverable' in place.
