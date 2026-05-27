from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp

from app.core.config import settings


def _is_transient_download_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    tokens = (
        "ssl",
        "unexpected_eof",
        "timed out",
        "timeout",
        "connection reset",
        "connection aborted",
        "502",
        "503",
        "504",
    )
    return any(token in msg for token in tokens)


def _ytdlp_extractor_args(*, for_download: bool) -> dict[str, Any]:
    clients = ["tv", "web", "android", "ios"] if for_download else ["android", "web"]
    args: dict[str, Any] = {"youtube": {"player_client": clients}}
    if settings.ytdlp_pot_base_url:
        args["youtubepot-bgutilhttp"] = {"base_url": settings.ytdlp_pot_base_url}
    return args


def _ytdlp_base_opts(*, for_download: bool = False) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": settings.ytdlp_socket_timeout_seconds,
        "extractor_args": _ytdlp_extractor_args(for_download=for_download),
    }
    if settings.ytdlp_proxy:
        opts["proxy"] = settings.ytdlp_proxy
    if settings.ytdlp_cookies_file:
        cookies_path = Path(settings.ytdlp_cookies_file)
        if cookies_path.is_file():
            opts["cookiefile"] = str(cookies_path)
    return opts


@dataclass(frozen=True)
class YtdlpSearchResult:
    source_kind: str
    source_id: str
    title: str
    artist: str
    duration_seconds: int | None
    thumbnail_url: str | None
    source_url: str
    tier: int
    license: str | None
    raw: dict[str, Any]


def _parse_artist_title(title: str) -> tuple[str, str]:
    for separator in (" - ", " – ", " — "):
        if separator in title:
            left, right = title.split(separator, 1)
            return left.strip(), right.strip()
    return "Unknown Artist", title.strip()


def _entry_to_result(
    entry: dict[str, Any], *, source_kind: str, tier: int
) -> YtdlpSearchResult | None:
    source_id = entry.get("id")
    if not source_id:
        return None
    title = str(entry.get("title") or "Unknown")
    artist, track_title = _parse_artist_title(title)
    if entry.get("artist"):
        artist = str(entry["artist"])
    if entry.get("track"):
        track_title = str(entry["track"])
    webpage_url = entry.get("webpage_url") or entry.get("url") or ""
    duration = entry.get("duration")
    return YtdlpSearchResult(
        source_kind=source_kind,
        source_id=str(source_id),
        title=track_title,
        artist=artist,
        duration_seconds=int(duration) if duration is not None else None,
        thumbnail_url=entry.get("thumbnail"),
        source_url=str(webpage_url),
        tier=tier,
        license=entry.get("license"),
        raw=entry,
    )


def search_entries(query: str, *, limit: int, include_soundcloud: bool) -> list[YtdlpSearchResult]:
    per_source = max(1, limit // 2) if include_soundcloud else limit
    results: list[YtdlpSearchResult] = []
    searches = [("youtube", f"ytsearch{per_source}:{query}", 2)]
    if include_soundcloud:
        searches.append(("soundcloud", f"scsearch{per_source}:{query}", 2))

    opts: dict[str, Any] = {
        **_ytdlp_base_opts(for_download=False),
        "skip_download": True,
        "extract_flat": "in_playlist",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        for source_kind, search_url, tier in searches:
            try:
                info = ydl.extract_info(search_url, download=False)
            except Exception:
                continue
            entries = info.get("entries") if isinstance(info, dict) else None
            if not entries:
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                parsed = _entry_to_result(entry, source_kind=source_kind, tier=tier)
                if parsed is not None:
                    results.append(parsed)
    return results[:limit]


def download_audio(source_url: str, output_template: str) -> str:
    last_error: BaseException | None = None
    for attempt in range(3):
        try:
            return _download_audio_once(source_url, output_template)
        except Exception as exc:
            last_error = exc
            if attempt >= 2 or not _is_transient_download_error(exc):
                raise
            time.sleep(2 * (attempt + 1))
    if last_error is not None:
        raise last_error
    msg = f"Download failed for {source_url}"
    raise RuntimeError(msg)


def _download_audio_once(source_url: str, output_template: str) -> str:
    opts: dict[str, Any] = {
        **_ytdlp_base_opts(for_download=True),
        "outtmpl": output_template,
        "format": "bestaudio[ext=m4a]/bestaudio/bestaudio/best/best",
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 3,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "opus",
                "preferredquality": "96",
            }
        ],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source_url, download=True)
        requested = info.get("requested_downloads") if isinstance(info, dict) else None
        if requested and isinstance(requested[0], dict) and requested[0].get("filepath"):
            return str(requested[0]["filepath"])
        filepath = info.get("filepath") if isinstance(info, dict) else None
        if filepath:
            return str(filepath)
        prepared = ydl.prepare_filename(info) if isinstance(info, dict) else output_template
        for suffix in (".opus", ".m4a", ".mp3", ".webm"):
            candidate = re.sub(r"\.[^.]+$", suffix, prepared)
            if Path(candidate).exists():
                return candidate
    msg = f"Downloaded file not found for {source_url}"
    raise FileNotFoundError(msg)
