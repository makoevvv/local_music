"""add auth tables, is_master, master protection triggers

Revision ID: 20260528_0002
Revises: 20260527_0001
Create Date: 2026-05-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260528_0002"
down_revision: str | None = "20260527_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_master", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "users_single_master_idx",
        "users",
        [sa.text("(1)")],
        unique=True,
        postgresql_where=sa.text("is_master = true"),
    )

    op.create_table(
        "invites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("used_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["used_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_kind", sa.String(), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_master_delete() RETURNS trigger AS $$
        BEGIN
          IF OLD.is_master THEN
            RAISE EXCEPTION 'master account cannot be deleted';
          END IF;
          RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_master_delete
          BEFORE DELETE ON users
          FOR EACH ROW EXECUTE FUNCTION prevent_master_delete();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_master_flag_change() RETURNS trigger AS $$
        BEGIN
          IF OLD.is_master IS DISTINCT FROM NEW.is_master THEN
            RAISE EXCEPTION 'is_master flag is immutable';
          END IF;
          IF OLD.is_master AND NEW.is_active = false THEN
            RAISE EXCEPTION 'master account cannot be deactivated';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_master_flag_change
          BEFORE UPDATE ON users
          FOR EACH ROW EXECUTE FUNCTION prevent_master_flag_change();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_master_flag_change ON users")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_master_delete ON users")
    op.execute("DROP FUNCTION IF EXISTS prevent_master_flag_change()")
    op.execute("DROP FUNCTION IF EXISTS prevent_master_delete()")

    op.drop_table("audit_log")
    op.drop_index("idx_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("invites")
    op.drop_index("users_single_master_idx", table_name="users")
    op.drop_column("users", "is_master")
