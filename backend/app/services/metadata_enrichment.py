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


def _external_http_client(*, timeout: float) -> httpx.Client:
    kwargs: dict[str, Any] = {"timeout": timeout}
    if settings.ytdlp_proxy:
        kwargs["proxy"] = settings.ytdlp_proxy
    return httpx.Client(**kwargs)


def _fetch_musicbrainz(artist: str, title: str) -> dict[str, Any] | None:
    query = f'recording:"{title}" AND artist:"{artist}"'
    headers = {"User-Agent": settings.musicbrainz_user_agent}
    try:
        with _external_http_client(timeout=15.0) as client:
            response = client.get(
                "https://musicbrainz.org/ws/2/recording",
                params={"query": query, "fmt": "json", "limit": 1},
                headers=headers,
            )
            if response.status_code != 200:
                return None
            recordings = response.json().get("recordings", [])
            return recordings[0] if recordings else None
    except Exception:
        return None


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
    try:
        _enrich_track_metadata_impl(session, track_id)
    except Exception:
        return


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _enrich_track_metadata_impl(session: Session, track_id: uuid.UUID) -> None:
    track = session.get(Track, track_id)
    if track is None or track.status != TrackStatus.ready:
        return

    main_artist_name = track.title
    artist_links = session.execute(
        select(TrackArtist).where(TrackArtist.track_id == track.id).order_by(TrackArtist.position)
    ).scalars()
    for link in artist_links:
        artist = session.get(Artist, link.artist_id)
        if artist is not None:
            main_artist_name = artist.name
            break

    recording = _fetch_musicbrainz(main_artist_name, track.title)
    if recording:
        track.mbid = recording.get("id")
        releases = recording.get("releases") or []
        if releases and track.album_id is None:
            release = releases[0]
            album_title = release.get("title") or track.title
            release_year = None
            date = release.get("date") or ""
            if len(date) >= 4 and date[:4].isdigit():
                release_year = int(date[:4])
            artist_entity = Artist(name=main_artist_name, sort_name=main_artist_name)
            session.add(artist_entity)
            session.flush()
            album = Album(
                title=album_title,
                primary_artist_id=artist_entity.id,
                release_year=release_year,
                is_single=False,
            )
            session.add(album)
            session.flush()
            track.album_id = album.id

    tags = _fetch_lastfm_tags(main_artist_name, track.title)
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
