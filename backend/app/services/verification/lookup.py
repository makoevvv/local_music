from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import settings


def _client() -> httpx.Client:
    kwargs: dict[str, Any] = {"timeout": 15.0}
    if settings.ytdlp_proxy:
        kwargs["proxy"] = settings.ytdlp_proxy
    return httpx.Client(**kwargs)


def _mb_headers() -> dict[str, str]:
    return {"User-Agent": settings.musicbrainz_user_agent}


def _as_dict(payload: object) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        return payload
    return None


def lookup_acoustid(
    fingerprint: str | None,
    duration_seconds: int | None,
) -> tuple[float, str | None, str | None, str | None]:
    """Return acoustid score, recording mbid, title, artist."""
    if not settings.acoustid_api_key or not fingerprint or not duration_seconds:
        return 0.0, None, None, None
    try:
        with _client() as client:
            response = client.get(
                "https://api.acoustid.org/v2/lookup",
                params={
                    "client": settings.acoustid_api_key,
                    "duration": int(duration_seconds),
                    "fingerprint": fingerprint,
                    "meta": "recordings",
                },
            )
    except Exception:
        return 0.0, None, None, None
    if response.status_code != 200:
        return 0.0, None, None, None
    body = _as_dict(response.json())
    if body is None or body.get("status") != "ok":
        return 0.0, None, None, None
    results = body.get("results")
    if not isinstance(results, list) or not results:
        return 0.0, None, None, None
    top = results[0] if isinstance(results[0], dict) else {}
    score_raw = top.get("score")
    score = float(score_raw) if isinstance(score_raw, int | float) else 0.0
    recordings = top.get("recordings")
    if not isinstance(recordings, list) or not recordings or not isinstance(recordings[0], dict):
        return min(1.0, max(0.0, score)), None, None, None
    recording = recordings[0]
    mbid = recording.get("id") if isinstance(recording.get("id"), str) else None
    title = recording.get("title") if isinstance(recording.get("title"), str) else None
    artist = None
    artists = recording.get("artists")
    if isinstance(artists, list) and artists and isinstance(artists[0], dict):
        name = artists[0].get("name")
        if isinstance(name, str):
            artist = name
    return min(1.0, max(0.0, score)), mbid, title, artist


def search_musicbrainz(
    artist: str,
    title: str,
) -> tuple[float, str | None, str | None, str | None]:
    """Return fuzzy score 0..1, recording mbid, title, artist. Empty when score < 0."""
    if not artist.strip() or not title.strip():
        return 0.0, None, None, None
    safe_artist = artist.replace('"', "")
    safe_title = title.replace('"', "")
    query = f'recording:"{safe_title}" AND artist:"{safe_artist}"'
    try:
        with _client() as client:
            response = client.get(
                "https://musicbrainz.org/ws/2/recording",
                params={"query": query, "fmt": "json", "limit": 1},
                headers=_mb_headers(),
            )
    except Exception:
        return 0.0, None, None, None
    if response.status_code != 200:
        return 0.0, None, None, None
    body = _as_dict(response.json())
    if body is None:
        return 0.0, None, None, None
    recordings = body.get("recordings")
    if not isinstance(recordings, list) or not recordings or not isinstance(recordings[0], dict):
        return 0.0, None, None, None
    recording = recordings[0]
    score_raw = recording.get("score")
    score = float(score_raw) / 100 if isinstance(score_raw, int | float) else 0.0
    mbid = recording.get("id") if isinstance(recording.get("id"), str) else None
    found_title = recording.get("title") if isinstance(recording.get("title"), str) else None
    found_artist = None
    credits = recording.get("artist-credit")
    if isinstance(credits, list):
        for credit in credits:
            if isinstance(credit, dict) and isinstance(credit.get("name"), str):
                found_artist = str(credit["name"])
                break
    return min(1.0, max(0.0, score)), mbid, found_title, found_artist


def fetch_recording_releases(mbid: str) -> list[dict[str, Any]]:
    time.sleep(1.1)
    try:
        with _client() as client:
            response = client.get(
                f"https://musicbrainz.org/ws/2/recording/{mbid}",
                params={"inc": "releases+release-groups", "fmt": "json"},
                headers=_mb_headers(),
            )
    except Exception:
        return []
    if response.status_code != 200:
        return []
    body = _as_dict(response.json())
    if body is None:
        return []
    releases = body.get("releases")
    if not isinstance(releases, list):
        return []
    return [item for item in releases if isinstance(item, dict)]


def fetch_lastfm_tags(artist: str, title: str) -> list[str]:
    if not settings.lastfm_api_key or not artist.strip() or not title.strip():
        return []
    try:
        with _client() as client:
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
    except Exception:
        return []
    if response.status_code != 200:
        return []
    body = _as_dict(response.json())
    if body is None:
        return []
    toptags = body.get("toptags")
    if not isinstance(toptags, dict):
        return []
    tags = toptags.get("tag")
    if not isinstance(tags, list):
        return []
    names: list[str] = []
    for tag in tags[:5]:
        if isinstance(tag, dict) and isinstance(tag.get("name"), str):
            names.append(str(tag["name"]))
    return names
