from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class SearchCandidatePublic(BaseModel):
    candidate_id: uuid.UUID
    title: str
    artist: str
    duration_seconds: int | None
    thumbnail_url: str | None
    source_kind: str
    source_id: str
    tier: int
    restricted: bool = False


class SearchResponse(BaseModel):
    query: str
    cached: bool
    items: list[SearchCandidatePublic]
    warning: str | None = None


class FromCandidateRequest(BaseModel):
    candidate_id: uuid.UUID


class FromCandidateResponse(BaseModel):
    track_id: uuid.UUID
    status: str


class TrackStatusResponse(BaseModel):
    track_id: uuid.UUID
    status: str
    error: str | None = None
    existing_track_id: uuid.UUID | None = None
