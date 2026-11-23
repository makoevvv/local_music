from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.imports.parser import ExternalTrack

SPOTIFY_AUTH = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN = "https://accounts.spotify.com/api/token"
SPOTIFY_API = "https://api.spotify.com/v1"


def spotify_configured() -> bool:
    return bool(settings.spotify_client_id and settings.spotify_client_secret)


def spotify_authorize_url(state: str) -> str:
    query = urlencode(
        {
            "client_id": settings.spotify_client_id or "",
            "response_type": "code",
            "redirect_uri": settings.spotify_redirect_uri,
            "scope": "user-library-read playlist-read-private",
            "state": state,
        }
    )
    return f"{SPOTIFY_AUTH}?{query}"


def exchange_spotify_code(code: str) -> dict[str, str]:
    response = httpx.post(
        SPOTIFY_TOKEN,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.spotify_redirect_uri,
        },
        auth=(settings.spotify_client_id or "", settings.spotify_client_secret or ""),
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        msg = "Spotify token response is missing access_token"
        raise ValueError(msg)
    return {
        "access_token": str(payload["access_token"]),
        "refresh_token": str(payload.get("refresh_token") or ""),
    }


def _spotify_track(item: dict[str, object], playlist_name: str) -> ExternalTrack | None:
    track = item.get("track") if isinstance(item.get("track"), dict) else item
    if not isinstance(track, dict):
        return None
    title = track.get("name")
    artists = track.get("artists")
    artist_name = ""
    if isinstance(artists, list) and artists and isinstance(artists[0], dict):
        artist_name = str(artists[0].get("name") or "")
    if not isinstance(title, str) or not artist_name:
        return None
    album = track.get("album")
    album_name = album.get("name") if isinstance(album, dict) else None
    external_ids = track.get("external_ids")
    isrc = external_ids.get("isrc") if isinstance(external_ids, dict) else None
    duration_ms = track.get("duration_ms")
    seconds = int(duration_ms) // 1000 if isinstance(duration_ms, int) else None
    return ExternalTrack(
        title=title,
        artist=artist_name,
        album=str(album_name) if isinstance(album_name, str) else None,
        isrc=str(isrc) if isinstance(isrc, str) else None,
        duration_seconds=seconds,
        playlist_name=playlist_name,
        external_id=str(track.get("id") or "") or None,
    )


def fetch_spotify_library(access_token: str) -> list[ExternalTrack]:
    headers = {"Authorization": f"Bearer {access_token}"}
    tracks: list[ExternalTrack] = []
    with httpx.Client(timeout=20.0, headers=headers) as client:
        saved = client.get(f"{SPOTIFY_API}/me/tracks", params={"limit": 50})
        saved.raise_for_status()
        body = saved.json()
        if isinstance(body, dict):
            for item in body.get("items") or []:
                if isinstance(item, dict):
                    parsed = _spotify_track(item, "Liked Songs")
                    if parsed is not None:
                        tracks.append(parsed)
        playlists = client.get(f"{SPOTIFY_API}/me/playlists", params={"limit": 20})
        playlists.raise_for_status()
        listing = playlists.json()
        if isinstance(listing, dict):
            for playlist in listing.get("items") or []:
                if not isinstance(playlist, dict):
                    continue
                name = str(playlist.get("name") or "Spotify")
                href = playlist.get("tracks")
                url = href.get("href") if isinstance(href, dict) else None
                if not isinstance(url, str):
                    continue
                page = client.get(url, params={"limit": 50})
                page.raise_for_status()
                page_body = page.json()
                if not isinstance(page_body, dict):
                    continue
                for item in page_body.get("items") or []:
                    if isinstance(item, dict):
                        parsed = _spotify_track(item, name)
                        if parsed is not None:
                            tracks.append(parsed)
    return tracks


def fetch_yandex_likes(access_token: str) -> list[ExternalTrack]:
    """Unofficial Yandex Music likes. The token is a user x-token, never a password."""
    response = httpx.get(
        "https://api.music.yandex.net/users/me/likes/tracks",
        headers={"Authorization": f"OAuth {access_token}"},
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    library = payload.get("result", {}).get("library") if isinstance(payload, dict) else None
    tracks = library.get("tracks") if isinstance(library, dict) else None
    parsed: list[ExternalTrack] = []
    if not isinstance(tracks, list):
        return parsed
    for item in tracks:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        artists = item.get("artists")
        artist = ""
        if isinstance(artists, list) and artists and isinstance(artists[0], dict):
            artist = str(artists[0].get("name") or "")
        if isinstance(title, str) and artist:
            parsed.append(
                ExternalTrack(
                    title=title,
                    artist=artist,
                    playlist_name="Yandex likes",
                    external_id=str(item.get("id") or "") or None,
                )
            )
    return parsed
