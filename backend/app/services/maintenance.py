from __future__ import annotations

import shutil
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.storage import resolve_track_file, storage_root
from app.core.sync_db import sync_session
from app.models.catalog import Album, Artist, Track, TrackArtist, TrackSource, TrackStatus
from app.services.album_resolution import resolve_album
from app.services.chromaprint import fingerprint_file
from app.services.source_matching.match import find_public_candidates, source_fingerprint_ok
from app.services.track_sources import build_track_source


def cleanup_uploads() -> dict[str, int]:
    root = storage_root() / "uploads"
    removed = 0
    if not root.exists():
        return {"removed": 0}
    cutoff = time.time() - settings.upload_session_ttl_seconds
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            modified = child.stat().st_mtime
        except OSError:
            continue
        if modified > cutoff:
            continue
        shutil.rmtree(child, ignore_errors=True)
        removed += 1
    return {"removed": removed}


def _artist_name(session: Session, track: Track) -> str:
    link = session.scalars(
        select(TrackArtist).where(TrackArtist.track_id == track.id).order_by(TrackArtist.position)
    ).first()
    if link is None:
        return "Unknown Artist"
    artist = session.get(Artist, link.artist_id)
    return artist.name if artist is not None else "Unknown Artist"


def _upsert_album(
    session: Session,
    *,
    title: str,
    artist_id: uuid.UUID | None,
    release_year: int | None,
    release_group_mbid: str | None,
    is_single: bool,
    cover_url: str | None,
) -> Album:
    if release_group_mbid:
        existing = session.scalar(select(Album).where(Album.mbid == release_group_mbid))
        if existing is not None:
            return existing
    album = Album(
        title=title,
        primary_artist_id=artist_id,
        mbid=release_group_mbid,
        release_year=release_year,
        is_single=is_single,
    )
    if cover_url:
        album.metadata_ = {"cover_url": cover_url}
    session.add(album)
    session.flush()
    return album


def reconcile_albums(*, limit: int = 50) -> dict[str, int]:
    checked = 0
    updated = 0
    with sync_session() as session:
        tracks = session.scalars(select(Track).where(Track.status == TrackStatus.ready)).all()
        for track in tracks:
            if checked >= limit:
                break
            meta = dict(track.metadata_ or {})
            album = session.get(Album, track.album_id) if track.album_id else None
            unresolved = meta.get("album_unresolved") is True
            single_without_id = bool(
                album and album.is_single and not track.mbid and not album.mbid
            )
            if not unresolved and not single_without_id:
                continue
            checked += 1
            decision = resolve_album(
                artist=_artist_name(session, track),
                title=track.title,
                recording_mbid=track.mbid,
            )
            if decision.unresolved:
                continue
            artist_id = album.primary_artist_id if album is not None else None
            if artist_id is None:
                link = session.scalars(
                    select(TrackArtist).where(TrackArtist.track_id == track.id)
                ).first()
                artist_id = link.artist_id if link is not None else None
            resolved = _upsert_album(
                session,
                title=decision.title,
                artist_id=artist_id,
                release_year=decision.release_year,
                release_group_mbid=decision.release_group_mbid,
                is_single=decision.is_single,
                cover_url=decision.cover_url,
            )
            track.album_id = resolved.id
            meta.pop("album_unresolved", None)
            track.metadata_ = meta
            if decision.recording_mbid and not track.mbid:
                clash = session.scalar(select(Track).where(Track.mbid == decision.recording_mbid))
                if clash is None:
                    track.mbid = decision.recording_mbid
            if decision.cover_url and not track.cover_url_origin:
                track.cover_url_origin = decision.cover_url
            updated += 1
    return {"checked": checked, "updated": updated}


def match_user_uploads(*, limit: int = 5) -> dict[str, int]:
    checked = 0
    added = 0
    with sync_session() as session:
        tracks = session.scalars(select(Track).where(Track.status == TrackStatus.ready)).all()
        for track in tracks:
            if checked >= limit:
                break
            sources = session.scalars(
                select(TrackSource).where(TrackSource.track_id == track.id)
            ).all()
            if not sources or any(item.source_kind != "user_upload" for item in sources):
                continue
            checked += 1
            candidates = find_public_candidates(
                query=f"{_artist_name(session, track)} - {track.title}",
                duration_seconds=track.duration_seconds,
                isrc=track.isrc,
            )
            if not candidates:
                continue
            try:
                audio_path = resolve_track_file(track.file_path)
            except FileNotFoundError:
                continue
            fingerprint = fingerprint_file(audio_path)
            local_raw = fingerprint.raw if fingerprint is not None else []
            work = storage_root() / "tmp" / f"match-{track.id}"
            primary_set = False
            try:
                for candidate in candidates:
                    if not source_fingerprint_ok(local_raw, candidate.url, work):
                        continue
                    already = any(
                        item.source_kind == candidate.kind and item.source_id == candidate.source_id
                        for item in sources
                    )
                    if already:
                        continue
                    priority = 10 if not primary_set else 20
                    primary_set = True
                    session.add(
                        build_track_source(
                            track_id=track.id,
                            source_kind=candidate.kind,
                            source_url=candidate.url,
                            source_id=candidate.source_id,
                            added_by_user_id=track.added_by_user_id,
                            recovery_priority=priority,
                            last_status="ok",
                        )
                    )
                    if priority == 10 and track.source_kind in {None, "user_upload", "upload"}:
                        track.source_kind = candidate.kind
                        track.source_url = candidate.url
                        track.source_id = candidate.source_id
                    added += 1
            finally:
                shutil.rmtree(work, ignore_errors=True)
    return {"checked": checked, "added": added}
