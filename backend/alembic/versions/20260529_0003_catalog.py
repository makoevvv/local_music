"""catalog tables and seed data

Revision ID: 20260529_0003
Revises: 20260528_0002
Create Date: 2026-05-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260529_0003"
down_revision: str | None = "20260528_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    track_status = postgresql.ENUM(
        "downloading", "ready", "failed", "blocked", name="track_status", create_type=False
    )
    artist_role = postgresql.ENUM("main", "feat", "remixer", name="artist_role", create_type=False)
    like_sentiment = postgresql.ENUM("like", "dislike", name="like_sentiment", create_type=False)

    op.execute("CREATE TYPE track_status AS ENUM ('downloading', 'ready', 'failed', 'blocked')")
    op.execute("CREATE TYPE artist_role AS ENUM ('main', 'feat', 'remixer')")
    op.execute("CREATE TYPE like_sentiment AS ENUM ('like', 'dislike')")

    op.create_table(
        "artists",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("mbid", sa.String(), nullable=True),
        sa.Column("sort_name", sa.String(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mbid"),
    )
    op.create_table(
        "albums",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("primary_artist_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mbid", sa.String(), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("cover_path", sa.String(), nullable=True),
        sa.Column("is_single", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["primary_artist_id"], ["artists.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mbid"),
    )
    op.create_table(
        "genres",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "languages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "tracks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("album_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_format", sa.String(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("audio_sha256", sa.String(), nullable=True),
        sa.Column("source_kind", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("mbid", sa.String(), nullable=True),
        sa.Column("isrc", sa.String(), nullable=True),
        sa.Column("explicit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_lyrics", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("bpm", sa.Float(), nullable=True),
        sa.Column("energy", sa.Float(), nullable=True),
        sa.Column("valence", sa.Float(), nullable=True),
        sa.Column("status", track_status, server_default="ready", nullable=False),
        sa.Column("added_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("play_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cover_url_origin", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["album_id"], ["albums.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audio_sha256"),
        sa.UniqueConstraint("mbid"),
    )
    op.create_index("idx_tracks_status", "tracks", ["status"])
    op.create_index("idx_tracks_created_at", "tracks", [sa.text("created_at DESC")])

    op.create_table(
        "track_artists",
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", artist_role, server_default="main", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"]),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("track_id", "artist_id", "role"),
    )
    op.create_table(
        "track_genres",
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("genre_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weight", sa.Float(), server_default="1.0", nullable=False),
        sa.ForeignKeyConstraint(["genre_id"], ["genres.id"]),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("track_id", "genre_id"),
    )
    op.create_table(
        "track_languages",
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["language_id"], ["languages.id"]),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("track_id", "language_id"),
    )
    op.create_table(
        "playlists",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_favourite", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("cover_path", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "playlists_owner_favourite_idx",
        "playlists",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("is_favourite = true"),
    )
    op.create_table(
        "playlist_tracks",
        sa.Column("playlist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("playlist_id", "track_id"),
    )
    op.create_table(
        "plays",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("listened_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_plays_user_started", "plays", ["user_id", sa.text("started_at DESC")])
    op.create_index("idx_plays_track", "plays", ["track_id"])
    op.create_table(
        "likes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("track_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sentiment", like_sentiment, nullable=False),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "track_id"),
    )

    genres = [
        ("rock", "Rock"),
        ("pop", "Pop"),
        ("hip-hop", "Hip-Hop"),
        ("electronic", "Electronic"),
        ("classical", "Classical"),
        ("jazz", "Jazz"),
        ("metal", "Metal"),
        ("ambient", "Ambient"),
        ("folk", "Folk"),
        ("soundtrack", "Soundtrack"),
    ]
    for slug, name in genres:
        op.execute(
            sa.text("INSERT INTO genres (slug, name) VALUES (:slug, :name)").bindparams(
                slug=slug, name=name
            )
        )

    languages = [
        ("en", "English"),
        ("ru", "Russian"),
        ("de", "German"),
        ("fr", "French"),
        ("es", "Spanish"),
        ("inst", "Instrumental"),
    ]
    for code, name in languages:
        op.execute(
            sa.text("INSERT INTO languages (code, name) VALUES (:code, :name)").bindparams(
                code=code, name=name
            )
        )


def downgrade() -> None:
    op.drop_table("likes")
    op.drop_index("idx_plays_track", table_name="plays")
    op.drop_index("idx_plays_user_started", table_name="plays")
    op.drop_table("plays")
    op.drop_table("playlist_tracks")
    op.drop_index("playlists_owner_favourite_idx", table_name="playlists")
    op.drop_table("playlists")
    op.drop_table("track_languages")
    op.drop_table("track_genres")
    op.drop_table("track_artists")
    op.drop_index("idx_tracks_created_at", table_name="tracks")
    op.drop_index("idx_tracks_status", table_name="tracks")
    op.drop_table("tracks")
    op.drop_table("languages")
    op.drop_table("genres")
    op.drop_table("albums")
    op.drop_table("artists")
    op.execute("DROP TYPE IF EXISTS like_sentiment")
    op.execute("DROP TYPE IF EXISTS artist_role")
    op.execute("DROP TYPE IF EXISTS track_status")
