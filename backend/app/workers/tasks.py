from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.storage import copy_track_file, storage_root
from app.core.sync_db import sync_session
from app.core.sync_redis import publish_track_event
from app.models.catalog import Track, TrackSource, TrackStatus
from app.models.search import SearchCandidate
from app.services.library_index import ExportOptions, LibraryIndexService, exports_root
from app.services.metadata_enrichment import enrich_track_metadata
from app.services.track_sources import mark_sources_status_sync, normalize_source_kind
from app.services.ytdlp import download_audio


def _publish(user_id: str, track_id: str, event: str, **extra: object) -> None:
    payload: dict[str, object] = {
        "event": event,
        "track_id": track_id,
        **extra,
    }
    publish_track_event(user_id, payload)


def download_track_job(track_id: str, candidate_id: str, user_id: str) -> None:
    track_uuid = uuid.UUID(track_id)
    candidate_uuid = uuid.UUID(candidate_id)

    with sync_session() as session:
        track = session.get(Track, track_uuid)
        candidate = session.get(SearchCandidate, candidate_uuid)
        if track is None or candidate is None:
            return

        source_kind = candidate.source_kind
        source_id = candidate.source_id
        _publish(user_id, track_id, "track.status_changed", status="downloading")

        try:
            source_url = str(candidate.payload.get("source_url") or "")
            if not source_url:
                raise RuntimeError("Candidate has no source URL")

            tmp_dir = storage_root() / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            output_template = str(tmp_dir / f"{track_id}.%(ext)s")
            downloaded_path = Path(download_audio(source_url, output_template))
            digest = hashlib.sha256(downloaded_path.read_bytes()).hexdigest()

            existing = session.execute(
                select(Track).where(Track.audio_sha256 == digest, Track.id != track.id)
            ).scalar_one_or_none()
            if existing is not None:
                downloaded_path.unlink(missing_ok=True)
                track.status = TrackStatus.failed
                track.metadata_ = {
                    "error": "duplicate",
                    "existing_track_id": str(existing.id),
                }
                track.updated_at = datetime.now(UTC)
                mark_sources_status_sync(
                    session,
                    track.id,
                    status="checksum_mismatch",
                    source_kind=source_kind,
                    source_id=source_id,
                )
                session.flush()
                _publish(
                    user_id,
                    track_id,
                    "track.failed",
                    status="failed",
                    error="duplicate",
                    existing_track_id=str(existing.id),
                )
                return

            relative, extension, size, file_digest = copy_track_file(downloaded_path, track.id)
            downloaded_path.unlink(missing_ok=True)

            track.file_path = relative
            track.file_format = extension
            track.file_size_bytes = size
            track.audio_sha256 = file_digest
            track.status = TrackStatus.ready
            track.updated_at = datetime.now(UTC)
            mark_sources_status_sync(
                session,
                track.id,
                status="ok",
                source_kind=source_kind,
                source_id=source_id,
            )
            session.flush()

            enrich_track_metadata(session, track.id)
            session.refresh(track)

            _publish(user_id, track_id, "track.ready", status="ready")
        except Exception as exc:
            session.rollback()
            track = session.get(Track, track_uuid)
            if track is None:
                return
            track.status = TrackStatus.failed
            track.metadata_ = {"error": str(exc)}
            track.updated_at = datetime.now(UTC)
            mark_sources_status_sync(
                session,
                track.id,
                status="gone",
                source_kind=source_kind,
                source_id=source_id,
            )
            session.flush()
            _publish(user_id, track_id, "track.failed", status="failed", error=str(exc))


def _run_async(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


def export_index_job(
    *,
    filename: str,
    minimal: bool = False,
    include_covers: bool = False,
    include_secrets: bool = False,
    no_plays: bool = False,
) -> str:
    from app.core.database import async_session_factory

    out = exports_root() / filename

    async def _export() -> int:
        async with async_session_factory() as session:
            result = await LibraryIndexService(session).export_index(
                ExportOptions(
                    out=out,
                    minimal=minimal,
                    include_covers=include_covers,
                    include_secrets=include_secrets,
                    no_plays=no_plays,
                )
            )
            return result.track_count

    track_count = _run_async(_export())
    return f"{filename}:{track_count}"


def restore_library_job(
    *,
    strategy: str = "best-source-first",
    concurrency: int = 2,
    dry_run: bool = False,
    track_ids: list[str] | None = None,
) -> dict[str, object]:
    from app.core.database import async_session_factory

    parsed_ids = [uuid.UUID(item) for item in track_ids] if track_ids else None

    async def _restore() -> dict[str, object]:
        async with async_session_factory() as session:
            result = await LibraryIndexService(session).restore_library(
                strategy=strategy,
                concurrency=concurrency,
                dry_run=dry_run,
                track_ids=parsed_ids,
            )
            return {
                "attempted": result.attempted,
                "restored": result.restored,
                "unrecoverable": result.unrecoverable,
                "skipped": result.skipped,
                "dry_run": result.dry_run,
            }

    return _run_async(_restore())  # type: ignore[return-value]


def verify_sources_job(*, limit: int = 200) -> dict[str, int]:
    checked = 0
    updated = 0
    with sync_session() as session:
        sources = session.scalars(
            select(TrackSource)
            .where(TrackSource.source_url.is_not(None))
            .order_by(TrackSource.last_checked_at.asc().nullsfirst())
            .limit(limit)
        ).all()
        for source in sources:
            url = source.source_url
            if not url:
                continue
            checked += 1
            status = _probe_source_url(url, source_kind=source.source_kind)
            source.last_status = status
            source.last_checked_at = datetime.now(UTC)
            updated += 1
        session.flush()
    return {"checked": checked, "updated": updated}


def _probe_source_url(url: str, *, source_kind: str | None) -> str:
    kind = normalize_source_kind(source_kind)
    if kind in {"youtube", "soundcloud", "bandcamp", "vimeo"}:
        try:
            import yt_dlp

            opts = {"quiet": True, "no_warnings": True, "skip_download": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                return "gone"
            availability = str(info.get("availability") or "").lower()
            if "private" in availability:
                return "private"
            if "premium" in availability or "subscriber" in availability:
                return "forbidden"
            return "ok"
        except Exception as exc:
            msg = str(exc).lower()
            if "private" in msg:
                return "private"
            if "geo" in msg or "blocked in your country" in msg:
                return "geo_blocked"
            if "403" in msg or "forbidden" in msg:
                return "forbidden"
            return "gone"

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.head(url)
            if response.status_code >= 400:
                response = client.get(url, headers={"Range": "bytes=0-0"})
            if response.status_code in {401, 403}:
                return "forbidden"
            if response.status_code == 404:
                return "gone"
            if response.status_code >= 400:
                return "gone"
            return "ok"
    except Exception:
        return "gone"


def cleanup_uploads_job() -> dict[str, int]:
    from app.services.maintenance import cleanup_uploads

    return cleanup_uploads()


def reconcile_albums_job(*, limit: int = 50) -> dict[str, int]:
    from app.services.maintenance import reconcile_albums

    return reconcile_albums(limit=limit)


def match_user_uploads_job(*, limit: int = 5) -> dict[str, int]:
    from app.services.maintenance import match_user_uploads

    return match_user_uploads(limit=limit)
