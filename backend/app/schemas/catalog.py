from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.catalog import LikeSentiment, TrackStatus


class ArtistBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class GenrePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class LanguagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str


class AlbumBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    release_year: int | None = None


class TrackListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    duration_seconds: int | None
    status: TrackStatus
    play_count: int
    has_lyrics: bool
    artists: list[ArtistBrief] = Field(default_factory=list)
    album: AlbumBrief | None = None
    user_sentiment: LikeSentiment | None = None


class TrackDetail(TrackListItem):
    file_format: str | None
    explicit: bool
    genres: list[GenrePublic] = Field(default_factory=list)
    languages: list[LanguagePublic] = Field(default_factory=list)
    created_at: datetime


class TrackListResponse(BaseModel):
    items: list[TrackListItem]
    page: int
    page_size: int
    total: int


class LikeRequest(BaseModel):
    sentiment: LikeSentiment = LikeSentiment.like


class PlaylistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    is_public: bool = False


class PlaylistUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_public: bool | None = None


class PlaylistTrackItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track: TrackListItem
    position: int
    added_at: datetime


class PlaylistSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_favourite: bool
    is_public: bool
    track_count: int = 0
    created_at: datetime


class PlaylistDetail(PlaylistSummary):
    tracks: list[PlaylistTrackItem] = Field(default_factory=list)


class PlaylistTracksRequest(BaseModel):
    track_ids: list[uuid.UUID]


class PlaylistReorderRequest(BaseModel):
    track_ids: list[uuid.UUID]


class PlayStartResponse(BaseModel):
    play_id: int


class PlayHeartbeatRequest(BaseModel):
    listened_seconds: int = Field(ge=0)
    completed: bool = False
