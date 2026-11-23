from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalTrack:
    title: str
    artist: str
    album: str | None = None
    isrc: str | None = None
    duration_seconds: int | None = None
    playlist_name: str = "Imported"
    external_id: str | None = None


def parse_import_payload(filename: str, raw: bytes) -> list[ExternalTrack]:
    text = raw.decode("utf-8-sig")
    lower = filename.lower()
    if lower.endswith(".json") or text.lstrip().startswith(("{", "[")):
        tracks = _parse_json(text)
    else:
        tracks = _parse_csv(text)
    return [item for item in tracks if item.title and item.artist]


def _parse_csv(text: str) -> list[ExternalTrack]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    fields = {name.strip().lower(): name for name in reader.fieldnames if name}
    tracks: list[ExternalTrack] = []
    for row in reader:
        title = _cell(row, fields, "title", "track", "song")
        artist = _cell(row, fields, "artist", "artist name", "artists")
        if not title or not artist:
            continue
        tracks.append(
            ExternalTrack(
                title=title,
                artist=artist,
                album=_cell(row, fields, "album"),
                isrc=_cell(row, fields, "isrc"),
                duration_seconds=_int_cell(row, fields, "duration_seconds", "duration"),
                playlist_name=_cell(row, fields, "playlist", "playlist name") or "Imported",
                external_id=_cell(row, fields, "id", "external_id"),
            )
        )
    return tracks


def _parse_json(text: str) -> list[ExternalTrack]:
    payload = json.loads(text)
    if isinstance(payload, list):
        return [_from_mapping(item, "Imported") for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("playlists"), list):
        tracks: list[ExternalTrack] = []
        for playlist in payload["playlists"]:
            if not isinstance(playlist, dict):
                continue
            name = str(playlist.get("name") or playlist.get("title") or "Imported")
            for item in playlist.get("tracks") or []:
                if isinstance(item, dict):
                    tracks.append(_from_mapping(item, name))
        return [item for item in tracks if item.title and item.artist]
    rows = payload.get("tracks") or payload.get("items") or []
    if isinstance(rows, list):
        return [_from_mapping(item, "Imported") for item in rows if isinstance(item, dict)]
    return []


def _from_mapping(item: dict[str, object], playlist_name: str) -> ExternalTrack:
    title = _text(item.get("title") or item.get("track") or item.get("name"))
    artist = _text(item.get("artist") or item.get("artistName") or item.get("artists"))
    artists = item.get("artists")
    if isinstance(artists, list) and artists:
        first = artists[0]
        if isinstance(first, dict):
            artist = _text(first.get("name")) or artist
        elif isinstance(first, str):
            artist = first
    duration = item.get("duration_seconds") or item.get("duration")
    seconds = int(duration) if isinstance(duration, int | float) else None
    named = _text(item.get("playlist") or item.get("playlist_name")) or playlist_name
    return ExternalTrack(
        title=title or "",
        artist=artist or "",
        album=_text(item.get("album")),
        isrc=_text(item.get("isrc")),
        duration_seconds=seconds,
        playlist_name=named,
        external_id=_text(item.get("id") or item.get("external_id")),
    )


def _cell(row: dict[str, str | None], fields: dict[str, str], *names: str) -> str | None:
    for name in names:
        source = fields.get(name)
        if source is None:
            continue
        value = row.get(source)
        if value and value.strip():
            return value.strip()
    return None


def _int_cell(row: dict[str, str | None], fields: dict[str, str], *names: str) -> int | None:
    raw = _cell(row, fields, *names)
    if raw is None:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
