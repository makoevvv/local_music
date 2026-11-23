from __future__ import annotations

import json
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ArtistRoleName = Literal["main", "feat", "remixer"]
TrustLevelName = Literal["high", "medium", "low", "none"]


class ArtistInput(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    role: ArtistRoleName = "main"


class UploadMeta(BaseModel):
    title: str | None = None
    artists: list[ArtistInput] = Field(default_factory=list)
    album: str | None = None
    year: int | None = None
    genres: list[str] = Field(default_factory=list)
    language: str | None = None
    instrumental: bool = False
    has_lyrics: bool | None = None

    @field_validator("title", "album", "language", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("year")
    @classmethod
    def _sane_year(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value < 1800 or value > 2100:
            return None
        return value

    @field_validator("genres")
    @classmethod
    def _clean_genres(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            name = item.strip()
            if name and name not in cleaned:
                cleaned.append(name)
        return cleaned[:8]


class ParsedMeta(UploadMeta):
    isrc: str | None = None
    duration_seconds: int | None = None
    has_cover: bool = False


class UploadCreateResponse(BaseModel):
    upload_id: uuid.UUID
    parsed_meta: ParsedMeta
    verification_pending: bool = True


class UploadSuggestions(BaseModel):
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    year: int | None = None
    mbid: str | None = None
    genres: list[str] = Field(default_factory=list)


class CandidateSource(BaseModel):
    kind: str
    source_id: str
    url: str
    match: float
    duration_delta: int | None = None
    title: str
    channel: str | None = None
    thumbnail: str | None = None

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.source_id}"


class AlbumResolution(BaseModel):
    title: str
    release_group_mbid: str | None = None
    release_year: int | None = None
    is_single: bool = False
    unresolved: bool = False
    cover_url: str | None = None
    recording_mbid: str | None = None


class VerificationResult(BaseModel):
    trust_level: TrustLevelName
    score: float
    suggestions: UploadSuggestions
    sources_verification: list[str] = Field(default_factory=list)
    candidate_sources: list[CandidateSource] = Field(default_factory=list)
    primary_source_index: int | None = None
    album_conflict: bool = False
    album_resolution: AlbumResolution | None = None
    recording_mbid: str | None = None


class ConfirmUploadRequest(BaseModel):
    meta: UploadMeta
    accept_suggestions: bool = False
    force: bool = False
    selected_source_ids: list[str] = Field(default_factory=list)
    primary_source_id: str | None = None


class ConfirmUploadResponse(BaseModel):
    track_id: uuid.UUID
    already_exists: bool = False
    rejected_source_ids: list[str] = Field(default_factory=list)


def parse_upload_meta(raw: str | None) -> UploadMeta:
    if raw is None or not raw.strip():
        return UploadMeta()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = "meta must be JSON"
        raise ValueError(msg) from exc
    if not isinstance(data, dict):
        msg = "meta must be a JSON object"
        raise ValueError(msg)
    if "artist" in data and "artists" not in data:
        artist_name = data.pop("artist")
        if isinstance(artist_name, str) and artist_name.strip():
            data["artists"] = [{"name": artist_name.strip(), "role": "main"}]
    return UploadMeta.model_validate(data)


def overlay_meta(parsed: UploadMeta, form: UploadMeta) -> UploadMeta:
    """Form fields that were sent replace parsed tags. A cleared album stays empty."""
    sent = form.model_fields_set
    return UploadMeta(
        title=form.title or parsed.title,
        artists=form.artists if "artists" in sent and form.artists else parsed.artists,
        album=form.album if "album" in sent else parsed.album,
        year=form.year if "year" in sent else parsed.year,
        genres=form.genres if "genres" in sent and form.genres else parsed.genres,
        language=form.language if "language" in sent else parsed.language,
        instrumental=form.instrumental if "instrumental" in sent else parsed.instrumental,
        has_lyrics=form.has_lyrics if "has_lyrics" in sent else parsed.has_lyrics,
    )
