from __future__ import annotations

from pathlib import Path

from app.schemas.upload import CandidateSource
from app.services.chromaprint import fingerprint_file, fingerprints_match
from app.services.source_matching.score import is_confirmed, match_score
from app.services.ytdlp import download_audio, search_entries


def find_public_candidates(
    *,
    query: str,
    duration_seconds: int | None,
    isrc: str | None,
) -> list[CandidateSource]:
    """Top confirmed YouTube/SoundCloud matches. ytsearch10 + scsearch10."""
    try:
        results = search_entries(query, limit=20, include_soundcloud=True)
    except Exception:
        return []

    ranked: list[CandidateSource] = []
    wanted_isrc = isrc.strip().upper() if isrc else None
    for result in results:
        delta: int | None = None
        if duration_seconds is not None and result.duration_seconds is not None:
            delta = int(result.duration_seconds) - int(duration_seconds)
        raw_isrc = result.raw.get("isrc") if isinstance(result.raw, dict) else None
        isrc_match = bool(
            wanted_isrc and isinstance(raw_isrc, str) and raw_isrc.strip().upper() == wanted_isrc
        )
        score = match_score(
            query=query,
            candidate_title=result.title,
            candidate_artist=result.artist,
            duration_delta=float(delta) if delta is not None else None,
            isrc_match=isrc_match,
        )
        if not is_confirmed(score, float(delta) if delta is not None else None):
            continue
        channel = None
        if isinstance(result.raw, dict):
            raw_channel = result.raw.get("channel") or result.raw.get("uploader")
            if isinstance(raw_channel, str):
                channel = raw_channel
        ranked.append(
            CandidateSource(
                kind=result.source_kind,
                source_id=result.source_id,
                url=result.source_url,
                match=round(score, 4),
                duration_delta=delta,
                title=result.title,
                channel=channel or result.artist,
                thumbnail=result.thumbnail_url,
            )
        )
    ranked.sort(key=lambda item: (-item.match, abs(item.duration_delta or 0)))
    return ranked[:3]


def source_fingerprint_ok(local_raw: list[int] | None, source_url: str, work_dir: Path) -> bool:
    """Download happens only on confirm. Reject the source when chromaprint is below 0.97."""
    if not local_raw or not source_url:
        return False
    work_dir.mkdir(parents=True, exist_ok=True)
    downloaded = Path(download_audio(source_url, str(work_dir / "candidate.%(ext)s")))
    try:
        other = fingerprint_file(downloaded)
        if other is None:
            return False
        return fingerprints_match(local_raw, other.raw)
    finally:
        downloaded.unlink(missing_ok=True)
