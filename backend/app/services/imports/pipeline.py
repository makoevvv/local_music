from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rq_queue import get_queue
from app.models.catalog import (
    Artist,
    ArtistRole,
    Playlist,
    PlaylistTrack,
    Track,
    TrackArtist,
    TrackStatus,
)
from app.models.imports import ImportItem, ImportJob
from app.models.search import SearchCandidate
from app.schemas.upload import CandidateSource
from app.services.artists import get_or_create_artist_sync
from app.services.source_matching.match import find_public_candidates
from app.services.source_matching.score import token_set_ratio


def schedule_public_download(
    session: Session,
    *,
    user_id: uuid.UUID,
    candidate: CandidateSource,
    title: str,
    artist: str,
) -> uuid.UUID:
    artist_row = get_or_create_artist_sync(session, artist)
    search_candidate = SearchCandidate(
        query_hash="import",
        source_kind=candidate.kind,
        source_id=candidate.source_id,
        tier=2,
        payload={
            "title": title,
            "artist": artist,
            "duration_seconds": None,
            "source_url": candidate.url,
            "thumbnail_url": candidate.thumbnail,
        },
    )
    session.add(search_candidate)
    session.flush()
    track = Track(
        title=title,
        file_path="pending",
        status=TrackStatus.downloading,
        source_kind=candidate.kind,
        source_url=candidate.url,
        source_id=candidate.source_id,
        added_by_user_id=user_id,
        metadata_={"imported_from_external": True, "candidate_id": str(search_candidate.id)},
    )
    session.add(track)
    session.flush()
    session.add(
        TrackArtist(track_id=track.id, artist_id=artist_row.id, role=ArtistRole.main, position=0)
    )
    from app.services.track_sources import build_track_source
    from app.workers.tasks import download_track_job

    session.add(
        build_track_source(
            track_id=track.id,
            source_kind=candidate.kind,
            source_url=candidate.url,
            source_id=candidate.source_id,
            added_by_user_id=user_id,
            tier=2,
        )
    )
    session.flush()
    try:
        get_queue().enqueue(
            download_track_job,
            str(track.id),
            str(search_candidate.id),
            str(user_id),
            job_timeout=600,
        )
    except Exception:
        return track.id
    return track.id


def _artist_name(session: Session, track: Track) -> str:
    link = session.scalars(
        select(TrackArtist).where(TrackArtist.track_id == track.id).order_by(TrackArtist.position)
    ).first()
    if link is None:
        return ""
    artist = session.get(Artist, link.artist_id)
    return artist.name if artist is not None else ""


def _local_isrc(session: Session, isrc: str) -> Track | None:
    return session.scalar(
        select(Track).where(
            func.lower(Track.isrc) == isrc.lower(),
            Track.status == TrackStatus.ready,
        )
    )


def _local_fuzzy(session: Session, artist: str, title: str, duration: int | None) -> Track | None:
    best: Track | None = None
    best_score = 0.0
    query = f"{artist} {title}"
    for track in session.scalars(select(Track).where(Track.status == TrackStatus.ready)).all():
        score = token_set_ratio(query, f"{_artist_name(session, track)} {track.title}")
        if (
            duration is not None
            and track.duration_seconds is not None
            and abs(duration - track.duration_seconds) > 5
        ):
            continue
        if score > best_score:
            best = track
            best_score = score
    if best is not None and best_score > 0.92:
        return best
    return None


def _candidate_payload(candidate: CandidateSource) -> dict[str, object]:
    return {
        "kind": candidate.kind,
        "source_id": candidate.source_id,
        "url": candidate.url,
        "title": candidate.title,
        "match": candidate.match,
        "duration_delta": candidate.duration_delta,
        "source_key": candidate.key,
    }


def _auto_match(candidate: CandidateSource, *, duration: int | None, threshold: float) -> bool:
    if candidate.match < threshold:
        return False
    if duration is None or candidate.duration_delta is None:
        return duration is None
    return abs(candidate.duration_delta) <= 2


def resolve_item(session: Session, item: ImportItem, job: ImportJob) -> None:
    if item.external_isrc:
        local = _local_isrc(session, item.external_isrc)
        if local is not None:
            item.status = "resolved"
            item.matched_track_id = local.id
            return
    fuzzy = _local_fuzzy(session, item.artist, item.title, item.duration_seconds)
    if fuzzy is not None:
        item.status = "resolved"
        item.matched_track_id = fuzzy.id
        return
    if settings.app_env != "test":
        import time

        time.sleep(1)
    found = find_public_candidates(
        query=f"{item.artist} - {item.title}",
        duration_seconds=item.duration_seconds,
        isrc=item.external_isrc,
    )
    item.candidates = [_candidate_payload(candidate) for candidate in found]
    if job.create_missing:
        for candidate in found:
            if _auto_match(candidate, duration=item.duration_seconds, threshold=job.auto_threshold):
                item.matched_track_id = schedule_public_download(
                    session,
                    user_id=job.user_id,
                    candidate=candidate,
                    title=item.title,
                    artist=item.artist,
                )
                item.status = "resolved"
                return
    if found:
        item.status = "ambiguous"
        return
    item.status = "failed"


def _playlist_external_id(job: ImportJob, name: str) -> str:
    digest = str((job.source_meta or {}).get("file_sha256") or job.id)
    return f"{job.provider}:{digest}:{name}"


def _get_or_create_playlist(session: Session, job: ImportJob, name: str) -> Playlist:
    external_id = _playlist_external_id(job, name)
    rows = session.scalars(select(Playlist).where(Playlist.owner_id == job.user_id)).all()
    for playlist in rows:
        marker = (playlist.metadata_ or {}).get("import")
        if isinstance(marker, dict) and marker.get("external_id") == external_id:
            if job.mode == "replace":
                session.execute(
                    delete(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist.id)
                )
            return playlist
    playlist = Playlist(
        owner_id=job.user_id,
        name=name,
        is_public=False,
        metadata_={
            "import": {
                "provider": job.provider,
                "external_id": external_id,
                "imported_at": datetime.now(UTC).isoformat(),
            }
        },
    )
    session.add(playlist)
    session.flush()
    return playlist


def _add_track(session: Session, playlist: Playlist, track_id: uuid.UUID) -> None:
    exists = session.scalar(
        select(PlaylistTrack).where(
            PlaylistTrack.playlist_id == playlist.id,
            PlaylistTrack.track_id == track_id,
        )
    )
    if exists is not None:
        return
    position = session.scalar(
        select(func.coalesce(func.max(PlaylistTrack.position), -1)).where(
            PlaylistTrack.playlist_id == playlist.id
        )
    )
    session.add(
        PlaylistTrack(
            playlist_id=playlist.id,
            track_id=track_id,
            position=int(position or -1) + 1,
        )
    )


def run_import_job(job_id: str) -> None:
    from app.core.sync_db import sync_session

    with sync_session() as session:
        job = session.get(ImportJob, uuid.UUID(job_id))
        if job is None or job.status in {"completed", "cancelled"}:
            return
        job.status = "running"
        session.flush()
        resolved = ambiguous = failed = 0
        playlists: dict[str, Playlist] = {}
        items = session.scalars(
            select(ImportItem).where(ImportItem.job_id == job.id).order_by(ImportItem.position)
        ).all()
        for item in items:
            session.refresh(job)
            if job.status == "cancelled":
                return
            if item.status == "resolved":
                resolved += 1
                continue
            resolve_item(session, item, job)
            if item.status == "resolved":
                resolved += 1
            elif item.status == "ambiguous":
                ambiguous += 1
            else:
                failed += 1
            if item.matched_track_id is not None:
                playlist = playlists.get(item.playlist_name)
                if playlist is None:
                    playlist = _get_or_create_playlist(session, job, item.playlist_name)
                    playlists[item.playlist_name] = playlist
                _add_track(session, playlist, item.matched_track_id)
        job.resolved_tracks = resolved
        job.ambiguous_tracks = ambiguous
        job.failed_tracks = failed
        job.total_tracks = len(items)
        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        job.result_summary = {
            "resolved": resolved,
            "ambiguous": ambiguous,
            "failed": failed,
            "playlists": [str(playlist.id) for playlist in playlists.values()],
        }


def enqueue_import(job_id: str) -> None:
    from app.workers.tasks import process_import_job

    get_queue().enqueue(process_import_job, job_id, job_timeout=3600)
