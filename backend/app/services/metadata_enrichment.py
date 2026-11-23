from __future__ import annotations

import re
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.catalog import (
    Album,
    Artist,
    Genre,
    Track,
    TrackArtist,
    TrackGenre,
    TrackStatus,
)
from app.schemas.upload import AlbumResolution
from app.services.album_resolution import resolve_album


def _external_http_client(*, timeout: float) -> httpx.Client:
    kwargs: dict[str, Any] = {"timeout": timeout}
    if settings.ytdlp_proxy:
        kwargs["proxy"] = settings.ytdlp_proxy
    return httpx.Client(**kwargs)


def _fetch_lastfm_tags(artist: str, title: str) -> list[str]:
    if not settings.lastfm_api_key:
        return []
    try:
        with _external_http_client(timeout=10.0) as client:
            response = client.get(
                "https://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "track.getTopTags",
                    "artist": artist,
                    "track": title,
                    "api_key": settings.lastfm_api_key,
                    "format": "json",
                },
            )
            if response.status_code != 200:
                return []
            tags = response.json().get("toptags", {}).get("tag", [])
            return [str(tag["name"]) for tag in tags[:5] if tag.get("name")]
    except Exception:
        return []


def enrich_track_metadata(session: Session, track_id: uuid.UUID) -> None:
    # Enrichment is best-effort. A failed flush (duplicate mbid, genre race) must
    # roll back only this savepoint; otherwise Postgres aborts the download transaction
    # and a track that already reached `ready` is marked failed.
    try:
        with session.begin_nested():
            _enrich_track_metadata_impl(session, track_id)
    except Exception:
        return


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _main_artist(session: Session, track: Track) -> tuple[str, uuid.UUID | None]:
    links = session.execute(
        select(TrackArtist).where(TrackArtist.track_id == track.id).order_by(TrackArtist.position)
    ).scalars()
    for link in links:
        artist = session.get(Artist, link.artist_id)
        if artist is not None and artist.name.strip():
            return artist.name, artist.id
    return "", None


def _album_for_decision(
    session: Session,
    decision: AlbumResolution,
    artist_id: uuid.UUID | None,
) -> Album:
    if decision.release_group_mbid:
        existing = session.scalar(select(Album).where(Album.mbid == decision.release_group_mbid))
        if existing is not None:
            return existing
    album = Album(
        title=decision.title,
        primary_artist_id=artist_id,
        mbid=decision.release_group_mbid,
        release_year=decision.release_year,
        is_single=decision.is_single,
    )
    if decision.cover_url:
        album.metadata_ = {"cover_url": decision.cover_url}
    session.add(album)
    session.flush()
    return album


def _apply_album_resolution(
    session: Session,
    track: Track,
    decision: AlbumResolution,
    artist_id: uuid.UUID | None,
) -> None:
    track.album_id = _album_for_decision(session, decision, artist_id).id
    meta = dict(track.metadata_ or {})
    if decision.unresolved:
        meta["album_unresolved"] = True
    else:
        meta.pop("album_unresolved", None)
    track.metadata_ = meta
    if decision.recording_mbid and not track.mbid:
        clash = session.scalar(select(Track).where(Track.mbid == decision.recording_mbid))
        if clash is None:
            track.mbid = decision.recording_mbid
    if decision.cover_url and not track.cover_url_origin:
        track.cover_url_origin = decision.cover_url


def _enrich_track_metadata_impl(session: Session, track_id: uuid.UUID) -> None:
    track = session.get(Track, track_id)
    if track is None or track.status != TrackStatus.ready:
        return

    artist_name, artist_id = _main_artist(session, track)
    if track.album_id is None:
        decision = resolve_album(
            artist=artist_name,
            title=track.title,
            recording_mbid=track.mbid,
        )
        _apply_album_resolution(session, track, decision, artist_id)

    tags = _fetch_lastfm_tags(artist_name or track.title, track.title)
    for tag_name in tags:
        slug = _slugify(tag_name)
        genre = session.execute(select(Genre).where(Genre.slug == slug)).scalar_one_or_none()
        if genre is None:
            genre = Genre(name=tag_name.title(), slug=slug)
            session.add(genre)
            session.flush()
        session.merge(TrackGenre(track_id=track.id, genre_id=genre.id, weight=1.0))

    if tags:
        instrumental_tags = {"instrumental", "ambient", "classical", "soundtrack"}
        if any(tag.lower() in instrumental_tags for tag in tags):
            track.has_lyrics = False

    session.flush()
