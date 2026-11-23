from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sync_redis import get_sync_redis
from app.models.catalog import Playlist, PlaylistTrack, Track, TrackStatus
from app.models.imports import ExternalAccount, ImportItem, ImportJob
from app.schemas.upload import CandidateSource
from app.services.imports.crypto import decrypt_token, encrypt_token
from app.services.imports.parser import ExternalTrack, parse_import_payload
from app.services.imports.pipeline import enqueue_import, schedule_public_download
from app.services.imports.providers import (
    exchange_spotify_code,
    fetch_spotify_library,
    fetch_yandex_likes,
    spotify_authorize_url,
    spotify_configured,
)


def _item_from_track(job_id: uuid.UUID, position: int, track: ExternalTrack) -> ImportItem:
    external_id = (
        track.external_id
        or f"{track.playlist_name}:{track.artist}:{track.title}:{track.isrc or position}"
    )
    return ImportItem(
        job_id=job_id,
        position=position,
        external_id=external_id,
        external_isrc=track.isrc,
        title=track.title,
        artist=track.artist,
        album=track.album,
        duration_seconds=track.duration_seconds,
        playlist_name=track.playlist_name or "Imported",
        status="pending",
    )


async def _existing_completed(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
    fingerprint: str,
    mode: str,
) -> ImportJob | None:
    rows = (
        await session.scalars(
            select(ImportJob)
            .where(
                ImportJob.user_id == user_id,
                ImportJob.provider == provider,
                ImportJob.mode == mode,
                ImportJob.status == "completed",
            )
            .order_by(ImportJob.created_at.desc())
        )
    ).all()
    for job in rows:
        if str((job.source_meta or {}).get("fingerprint") or "") == fingerprint:
            return job
    return None


async def create_job(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
    tracks: list[ExternalTrack],
    source_meta: dict[str, object],
    mode: str,
    auto_threshold: float,
    create_missing: bool,
) -> ImportJob:
    fingerprint = str(source_meta.get("fingerprint") or "")
    if fingerprint:
        existing = await _existing_completed(
            session,
            user_id=user_id,
            provider=provider,
            fingerprint=fingerprint,
            mode=mode,
        )
        if existing is not None:
            return existing
    job = ImportJob(
        user_id=user_id,
        provider=provider,
        source_meta=source_meta,
        status="queued",
        mode=mode,
        auto_threshold=auto_threshold,
        create_missing=create_missing,
        total_tracks=len(tracks),
    )
    session.add(job)
    await session.flush()
    for position, track in enumerate(tracks):
        session.add(_item_from_track(job.id, position, track))
    await session.commit()
    enqueue_import(str(job.id))
    await session.refresh(job)
    return job


async def create_file_job(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    filename: str,
    raw: bytes,
    mode: str,
    auto_threshold: float,
    create_missing: bool,
) -> ImportJob:
    tracks = parse_import_payload(filename, raw)
    if not tracks:
        msg = "No tracks found in the file"
        raise ValueError(msg)
    digest = hashlib.sha256(raw).hexdigest()
    return await create_job(
        session,
        user_id=user_id,
        provider="file",
        tracks=tracks,
        source_meta={"filename": filename, "fingerprint": digest, "rows": len(tracks)},
        mode=mode,
        auto_threshold=auto_threshold,
        create_missing=create_missing,
    )


def remember_oauth_state(user_id: uuid.UUID) -> str:
    state = secrets.token_urlsafe(24)
    get_sync_redis().setex(f"import:oauth:{state}", 600, str(user_id))
    return state


def consume_oauth_state(state: str) -> uuid.UUID | None:
    key = f"import:oauth:{state}"
    raw = get_sync_redis().get(key)
    if raw is None:
        return None
    get_sync_redis().delete(key)
    return uuid.UUID(raw)


async def save_account(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
    access_token: str,
    refresh_token: str | None,
    external_user_id: str | None,
) -> ExternalAccount:
    account = await session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user_id,
            ExternalAccount.provider == provider,
        )
    )
    access = encrypt_token(access_token)
    refresh = encrypt_token(refresh_token) if refresh_token else None
    if account is None:
        account = ExternalAccount(
            user_id=user_id,
            provider=provider,
            external_user_id=external_user_id,
            access_token_enc=access,
            refresh_token_enc=refresh,
        )
        session.add(account)
    else:
        account.access_token_enc = access
        account.refresh_token_enc = refresh
        account.external_user_id = external_user_id or account.external_user_id
        account.updated_at = datetime.now(UTC)
    await session.commit()
    return account


async def start_provider_job(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    provider: str,
    mode: str,
    auto_threshold: float,
    create_missing: bool,
) -> ImportJob:
    account = await session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user_id,
            ExternalAccount.provider == provider,
        )
    )
    if account is None:
        msg = f"{provider} is not connected"
        raise ValueError(msg)
    token = decrypt_token(account.access_token_enc)
    if provider == "spotify":
        tracks = fetch_spotify_library(token)
    elif provider == "yandex":
        tracks = fetch_yandex_likes(token)
    else:
        msg = f"Unsupported provider {provider}"
        raise ValueError(msg)
    body = "|".join(
        f"{track.playlist_name}:{track.artist}:{track.title}:{track.isrc or ''}" for track in tracks
    )
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    return await create_job(
        session,
        user_id=user_id,
        provider=provider,
        tracks=tracks,
        source_meta={"fingerprint": fingerprint, "rows": len(tracks)},
        mode=mode,
        auto_threshold=auto_threshold,
        create_missing=create_missing,
    )


def spotify_connect_url(user_id: uuid.UUID) -> str:
    if not spotify_configured():
        msg = "Spotify OAuth is not configured"
        raise ValueError(msg)
    return spotify_authorize_url(remember_oauth_state(user_id))


async def finish_spotify_callback(session: AsyncSession, *, code: str, state: str) -> None:
    user_id = consume_oauth_state(state)
    if user_id is None:
        msg = "OAuth state expired"
        raise ValueError(msg)
    tokens = exchange_spotify_code(code)
    await save_account(
        session,
        user_id=user_id,
        provider="spotify",
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"] or None,
        external_user_id=None,
    )


async def resolve_item_choice(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    item_id: uuid.UUID,
    track_id: uuid.UUID | None,
    source_key: str | None,
) -> ImportItem:
    job = await session.get(ImportJob, job_id)
    if job is None or job.user_id != user_id:
        msg = "Import job not found"
        raise LookupError(msg)
    item = await session.get(ImportItem, item_id)
    if item is None or item.job_id != job.id:
        msg = "Import item not found"
        raise LookupError(msg)
    if track_id is not None:
        track = await session.get(Track, track_id)
        if track is None or track.status not in {TrackStatus.ready, TrackStatus.downloading}:
            msg = "Track not found"
            raise LookupError(msg)
        item.matched_track_id = track.id
    elif source_key:
        chosen = next(
            (
                candidate
                for candidate in item.candidates
                if candidate.get("source_key") == source_key
            ),
            None,
        )
        if chosen is None:
            msg = "Candidate not found"
            raise LookupError(msg)
        from app.core.sync_db import sync_session

        candidate = CandidateSource.model_validate(chosen)
        with sync_session() as sync:
            matched = schedule_public_download(
                sync,
                user_id=user_id,
                candidate=candidate,
                title=item.title,
                artist=item.artist,
            )
        item.matched_track_id = matched
    else:
        msg = "Choose a track or a source"
        raise ValueError(msg)
    item.status = "resolved"
    playlist = await _playlist_for_item(session, job, item.playlist_name)
    await _link_track(session, playlist.id, item.matched_track_id)
    job.resolved_tracks += 1
    if job.ambiguous_tracks > 0:
        job.ambiguous_tracks -= 1
    await session.commit()
    return item


async def _playlist_for_item(session: AsyncSession, job: ImportJob, name: str) -> Playlist:
    digest = str((job.source_meta or {}).get("fingerprint") or job.id)
    external_id = f"{job.provider}:{digest}:{name}"
    rows = (await session.scalars(select(Playlist).where(Playlist.owner_id == job.user_id))).all()
    for playlist in rows:
        marker = (playlist.metadata_ or {}).get("import")
        if isinstance(marker, dict) and marker.get("external_id") == external_id:
            return playlist
    playlist = Playlist(
        owner_id=job.user_id,
        name=name,
        metadata_={
            "import": {
                "provider": job.provider,
                "external_id": external_id,
                "imported_at": datetime.now(UTC).isoformat(),
            }
        },
    )
    session.add(playlist)
    await session.flush()
    return playlist


async def _link_track(
    session: AsyncSession, playlist_id: uuid.UUID, track_id: uuid.UUID | None
) -> None:
    if track_id is None:
        return
    existing = await session.scalar(
        select(PlaylistTrack).where(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id == track_id,
        )
    )
    if existing is not None:
        return
    position = await session.scalar(
        select(func.max(PlaylistTrack.position)).where(PlaylistTrack.playlist_id == playlist_id)
    )
    session.add(
        PlaylistTrack(
            playlist_id=playlist_id,
            track_id=track_id,
            position=0 if position is None else int(position) + 1,
        )
    )
