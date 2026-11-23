from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.core.storage import copy_track_file, storage_root
from app.core.sync_db import sync_session
from app.core.sync_redis import publish_track_event
from app.models.catalog import Track, TrackStatus
from app.models.search import SearchCandidate
from app.services.metadata_enrichment import enrich_track_metadata
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
            session.flush()
            _publish(user_id, track_id, "track.failed", status="failed", error=str(exc))
