"""external accounts and import jobs

Revision ID: 20261124_0006
Revises: 20260808_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261124_0006"
down_revision: str | None = "20260808_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "playlists",
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_table(
        "external_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("external_user_id", sa.String(), nullable=True),
        sa.Column("access_token_enc", postgresql.BYTEA(), nullable=False),
        sa.Column("refresh_token_enc", postgresql.BYTEA(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="external_accounts_user_provider"),
    )
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("source_meta", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("mode", sa.String(), nullable=False, server_default="add"),
        sa.Column("auto_threshold", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("create_missing", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("total_tracks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_tracks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ambiguous_tracks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_tracks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_import_jobs_user", "import_jobs", ["user_id", "created_at"])
    op.create_table(
        "import_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("external_isrc", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("artist", sa.String(), nullable=False),
        sa.Column("album", sa.String(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("playlist_name", sa.String(), nullable=False, server_default="Imported"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("matched_track_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidates", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["import_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_track_id"], ["tracks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_import_items_job", "import_items", ["job_id", "position"])


def downgrade() -> None:
    op.drop_index("idx_import_items_job", table_name="import_items")
    op.drop_table("import_items")
    op.drop_index("idx_import_jobs_user", table_name="import_jobs")
    op.drop_table("import_jobs")
    op.drop_table("external_accounts")
    op.drop_column("playlists", "metadata")
