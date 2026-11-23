"""unique track_sources (track_id, source_kind, source_id)

Revision ID: 20261124_0008
Revises: 20261124_0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261124_0008"
down_revision: str | None = "20261124_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # NULL source_id values compare equal, matching NULLS NOT DISTINCT below.
    op.execute(
        """
        DELETE FROM track_sources
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY track_id, source_kind, source_id
                        ORDER BY added_at ASC, id ASC
                    ) AS rn
                FROM track_sources
            ) ranked
            WHERE rn > 1
        )
        """
    )
    op.create_index(
        "uq_track_sources_track_kind_id",
        "track_sources",
        ["track_id", "source_kind", "source_id"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_index("uq_track_sources_track_kind_id", table_name="track_sources")
