from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.schemas.upload import ArtistInput, ParsedMeta

_TITLE_KEYS = ("TIT2", "\xa9nam", "title", "TITLE")
_ARTIST_KEYS = ("TPE1", "\xa9ART", "artist", "ARTIST")
_ALBUM_KEYS = ("TALB", "\xa9alb", "album", "ALBUM")
_DATE_KEYS = ("TDRC", "TDRL", "\xa9day", "date", "DATE", "year", "YEAR")
_GENRE_KEYS = ("TCON", "\xa9gen", "genre", "GENRE")
_ISRC_KEYS = ("TSRC", "isrc", "ISRC")

ALLOWED_AUDIO_EXTENSIONS = {"mp3", "m4a", "aac", "flac", "ogg", "opus", "wav"}
ALLOWED_COVER_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


@dataclass
class AudioProbe:
    meta: ParsedMeta
    original_tags: dict[str, str] = field(default_factory=dict)
    duration_seconds: int | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    cover_bytes: bytes | None = None
    cover_extension: str | None = None


def _tag_text(value: object) -> str | None:
    if value is None:
        return None
    text = getattr(value, "text", None)
    if text:
        if isinstance(text, list):
            return str(text[0]).strip() if text else None
        return str(text).strip() or None
    if isinstance(value, list):
        return str(value[0]).strip() if value else None
    rendered = str(value).strip()
    return rendered or None


def _first_tag(tags: Any, keys: tuple[str, ...]) -> str | None:
    if tags is None:
        return None
    for key in keys:
        try:
            if key in tags:
                found = _tag_text(tags[key])
                if found:
                    return found
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _year_from_tag(value: str | None) -> int | None:
    if not value:
        return None
    digits = ""
    for char in value:
        if char.isdigit():
            digits += char
            if len(digits) == 4:
                break
        elif digits:
            break
    if len(digits) != 4:
        return None
    year = int(digits)
    if year < 1800 or year > 2100:
        return None
    return year


def _cover_from_audio(audio: Any) -> tuple[bytes | None, str | None]:
    pictures = getattr(audio, "pictures", None) or []
    if pictures:
        picture = pictures[0]
        data = getattr(picture, "data", None)
        mime = str(getattr(picture, "mime", "") or "")
        if isinstance(data, bytes) and data:
            return data, _extension_for_mime(mime)
    tags = getattr(audio, "tags", None)
    if tags is None:
        return None, None
    try:
        keys = list(tags.keys())
    except (AttributeError, TypeError):
        return None, None
    for key in keys:
        if not str(key).startswith("APIC"):
            continue
        try:
            picture = tags[key]
        except (KeyError, TypeError):
            continue
        data = getattr(picture, "data", None)
        mime = str(getattr(picture, "mime", "") or "")
        if isinstance(data, bytes) and data:
            return data, _extension_for_mime(mime)
    return None, None


def _extension_for_mime(mime: str) -> str:
    lowered = mime.lower()
    if "png" in lowered:
        return "png"
    if "webp" in lowered:
        return "webp"
    return "jpg"


def _wav_duration(path: Path) -> int | None:
    import wave

    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            if rate <= 0:
                return None
            return int(handle.getnframes() / rate)
    except (wave.Error, EOFError, OSError):
        return None


def probe_audio(path: Path) -> AudioProbe:
    from mutagen import File as MutagenFile  # type: ignore[attr-defined]

    original: dict[str, str] = {}
    try:
        audio = MutagenFile(path, easy=False)
    except Exception:
        audio = None
    title = artist = album = isrc = None
    year = None
    genres: list[str] = []
    duration = bitrate = sample_rate = None
    cover_bytes = None
    cover_extension = None
    if audio is not None:
        tags = getattr(audio, "tags", None)
        title = _first_tag(tags, _TITLE_KEYS)
        artist = _first_tag(tags, _ARTIST_KEYS)
        album = _first_tag(tags, _ALBUM_KEYS)
        year = _year_from_tag(_first_tag(tags, _DATE_KEYS))
        genre_raw = _first_tag(tags, _GENRE_KEYS)
        if genre_raw:
            genres = [
                part.strip() for part in genre_raw.replace("/", ";").split(";") if part.strip()
            ]
        isrc = _first_tag(tags, _ISRC_KEYS)
        info = getattr(audio, "info", None)
        if info is not None:
            length = getattr(info, "length", None)
            if isinstance(length, int | float) and length > 0:
                duration = int(round(length))
            raw_bitrate = getattr(info, "bitrate", None)
            if isinstance(raw_bitrate, int):
                bitrate = raw_bitrate
            raw_rate = getattr(info, "sample_rate", None)
            if isinstance(raw_rate, int):
                sample_rate = raw_rate
        cover_bytes, cover_extension = _cover_from_audio(audio)
        for key, label in (
            ("title", title),
            ("artist", artist),
            ("album", album),
            ("isrc", isrc),
        ):
            if label:
                original[key] = label
        if year:
            original["year"] = str(year)
    if duration is None and path.suffix.lower() == ".wav":
        duration = _wav_duration(path)
    artists = [ArtistInput(name=artist, role="main")] if artist else []
    meta = ParsedMeta(
        title=title,
        artists=artists,
        album=album,
        year=year,
        genres=genres[:8],
        isrc=isrc,
        duration_seconds=duration,
        has_cover=cover_bytes is not None,
    )
    return AudioProbe(
        meta=meta,
        original_tags=original,
        duration_seconds=duration,
        bitrate=bitrate,
        sample_rate=sample_rate,
        cover_bytes=cover_bytes,
        cover_extension=cover_extension,
    )
