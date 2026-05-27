from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TrackStatus(str, enum.Enum):
    downloading = "downloading"
    ready = "ready"
    failed = "failed"
    blocked = "blocked"


class ArtistRole(str, enum.Enum):
    main = "main"
    feat = "feat"
    remixer = "remixer"


class LikeSentiment(str, enum.Enum):
    like = "like"
    dislike = "dislike"


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    mbid: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    sort_name: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    primary_artist_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id"), nullable=True
    )
    mbid: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String, nullable=True)
    is_single: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    album_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("albums.id"), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_format: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    audio_sha256: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    source_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    mbid: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    isrc: Mapped[str | None] = mapped_column(String, nullable=True)
    explicit: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    has_lyrics: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    valence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[TrackStatus] = mapped_column(
        Enum(TrackStatus, name="track_status", native_enum=True),
        nullable=False,
        server_default=TrackStatus.ready,
    )
    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    play_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cover_url_origin: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    album: Mapped[Album | None] = relationship("Album")
    artists: Mapped[list[TrackArtist]] = relationship(back_populates="track")


class TrackArtist(Base):
    __tablename__ = "track_artists"

    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    artist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artists.id"), primary_key=True
    )
    role: Mapped[ArtistRole] = mapped_column(
        Enum(ArtistRole, name="artist_role", native_enum=True),
        primary_key=True,
        server_default=ArtistRole.main,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    track: Mapped[Track] = relationship(back_populates="artists")
    artist: Mapped[Artist] = relationship()


class TrackGenre(Base):
    __tablename__ = "track_genres"

    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("genres.id"), primary_key=True
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")


class TrackLanguage(Base):
    __tablename__ = "track_languages"

    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    language_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("languages.id"), primary_key=True
    )


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_favourite: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    cover_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tracks: Mapped[list[PlaylistTrack]] = relationship(
        back_populates="playlist",
        order_by="PlaylistTrack.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    playlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    playlist: Mapped[Playlist] = relationship(back_populates="tracks")
    track: Mapped[Track] = relationship()


class Play(Base):
    __tablename__ = "plays"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    listened_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    source: Mapped[str | None] = mapped_column(Text, nullable=True)


class Like(Base):
    __tablename__ = "likes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sentiment: Mapped[LikeSentiment] = mapped_column(
        Enum(LikeSentiment, name="like_sentiment", native_enum=True), nullable=False
    )
