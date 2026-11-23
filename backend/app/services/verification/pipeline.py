from __future__ import annotations

from typing import Any

from app.schemas.upload import (
    AlbumResolution,
    CandidateSource,
    UploadMeta,
    UploadSuggestions,
    VerificationResult,
)
from app.services.album_resolution import decision_from_releases, unresolved_album
from app.services.source_matching.match import find_public_candidates
from app.services.verification.lookup import (
    fetch_lastfm_tags,
    fetch_recording_releases,
    lookup_acoustid,
    search_musicbrainz,
)
from app.services.verification.scoring import combine_trust, heuristic_bonus, trust_level


def _query(meta: UploadMeta) -> str:
    artist = meta.artists[0].name if meta.artists else ""
    title = meta.title or ""
    if artist and title:
        return f"{artist} - {title}"
    return artist or title


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    return None


def build_verification(session_data: dict[str, Any], meta: UploadMeta) -> VerificationResult:
    fingerprint = session_data.get("fingerprint")
    compressed = fingerprint if isinstance(fingerprint, str) else None
    duration = _int_or_none(session_data.get("duration_seconds"))
    artist = meta.artists[0].name if meta.artists else ""
    title = meta.title or ""

    acoustid_score, acoustid_mbid, acoustid_title, acoustid_artist = lookup_acoustid(
        compressed, duration
    )
    mb_score, mb_mbid, mb_title, mb_artist = search_musicbrainz(artist, title)

    sources: list[str] = []
    if acoustid_score > 0:
        sources.append("acoustid")
    if mb_score > 0:
        sources.append("musicbrainz")

    original_tags = session_data.get("original_tags")
    has_tags = isinstance(original_tags, dict) and bool(original_tags)
    bonus = heuristic_bonus(
        has_tags=has_tags,
        year=meta.year,
        duration_seconds=duration,
        bitrate=_int_or_none(session_data.get("bitrate")),
        sample_rate=_int_or_none(session_data.get("sample_rate")),
    )
    if bonus > 0:
        sources.append("heuristics")

    level_without_lastfm = trust_level(
        combine_trust(
            acoustid_score=acoustid_score,
            musicbrainz_score=mb_score,
            bonus=bonus,
        )
    )

    recording_mbid = None
    if acoustid_mbid and level_without_lastfm in {"high", "medium"}:
        recording_mbid = acoustid_mbid
    elif mb_mbid and mb_score >= 0.9:
        recording_mbid = mb_mbid

    resolution: AlbumResolution
    if recording_mbid:
        releases = fetch_recording_releases(recording_mbid)
        resolution = decision_from_releases(releases, title or "Unknown", recording_mbid)
    else:
        resolution = unresolved_album(title or "Unknown", None)

    suggestion_artist = acoustid_artist or mb_artist
    suggestion_title = acoustid_title or mb_title
    tag_artist = suggestion_artist or artist
    tag_title = suggestion_title or title
    genres = fetch_lastfm_tags(tag_artist, tag_title)
    if genres:
        sources.append("lastfm")
        bonus += 0.05

    score = round(
        combine_trust(acoustid_score=acoustid_score, musicbrainz_score=mb_score, bonus=bonus),
        4,
    )
    level = trust_level(score)
    suggested_album = None if resolution.unresolved else resolution.title
    user_album = (meta.album or "").casefold()
    album_conflict = bool(
        user_album
        and suggested_album
        and user_album != suggested_album.casefold()
        and level == "high"
    )

    candidates: list[CandidateSource] = []
    query = _query(meta)
    if query:
        isrc = session_data.get("isrc")
        candidates = find_public_candidates(
            query=query,
            duration_seconds=duration,
            isrc=isrc if isinstance(isrc, str) else None,
        )

    return VerificationResult(
        trust_level=level,
        score=score,
        suggestions=UploadSuggestions(
            title=suggestion_title,
            artist=suggestion_artist,
            album=suggested_album,
            year=resolution.release_year,
            mbid=recording_mbid,
            genres=genres,
        ),
        sources_verification=sources,
        candidate_sources=candidates,
        primary_source_index=0 if candidates else None,
        album_conflict=album_conflict,
        album_resolution=resolution,
        recording_mbid=recording_mbid,
    )
