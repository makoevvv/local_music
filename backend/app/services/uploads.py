from __future__ import annotations

import asyncio
import hashlib
import shutil
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import copy_track_file, save_cover_file, storage_root
from app.models.catalog import (
    Album,
    Artist,
    ArtistRole,
    Genre,
    Language,
    Track,
    TrackArtist,
    TrackGenre,
    TrackLanguage,
    TrackSource,
    TrackStatus,
)
from app.schemas.upload import (
    AlbumResolution,
    ArtistInput,
    ConfirmUploadRequest,
    ConfirmUploadResponse,
    ParsedMeta,
    UploadCreateResponse,
    UploadMeta,
    VerificationResult,
    overlay_meta,
)
from app.services.artists import get_or_create_artist
from app.services.audio_tags import (
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_COVER_EXTENSIONS,
    probe_audio,
)
from app.services.chromaprint import fingerprint_file
from app.services.source_matching.match import source_fingerprint_ok
from app.services.track_sources import build_track_source
from app.services.upload_store import (
    delete_session,
    load_fingerprint_cache,
    load_session,
    load_verification_cache,
    save_fingerprint_cache,
    save_session,
    save_verification_cache,
)
from app.services.verification.pipeline import build_verification

_USER_UPLOAD_PRIORITY = 100
_PRIMARY_PRIORITY = 10
_BACKUP_PRIORITY = 20


def _extension(filename: str | None) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def _slugify(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _query(meta: UploadMeta) -> str:
    artist = meta.artists[0].name if meta.artists else ""
    title = meta.title or ""
    if artist and title:
        return f"{artist} - {title}"
    return artist or title


def _ensure_fingerprint(data: dict[str, Any]) -> None:
    raw = data.get("fingerprint_raw")
    if isinstance(raw, list) and raw:
        return
    cached = load_fingerprint_cache(str(data["sha256"]))
    cached_raw = cached.get("fingerprint_raw") if cached else None
    if isinstance(cached_raw, list) and cached_raw:
        data["fingerprint"] = cached.get("fingerprint") if cached else None
        data["fingerprint_raw"] = cached_raw
        return
    fp = fingerprint_file(storage_root() / str(data["relative_path"]))
    if fp is None:
        data["fingerprint"] = None
        data["fingerprint_raw"] = []
        return
    data["fingerprint"] = fp.compressed
    data["fingerprint_raw"] = fp.raw
    if fp.duration_seconds and not data.get("duration_seconds"):
        data["duration_seconds"] = fp.duration_seconds
    save_fingerprint_cache(str(data["sha256"]), fp.compressed, [int(item) for item in fp.raw])


def _schedule_cleanup() -> None:
    from app.core.rq_queue import get_queue
    from app.workers.tasks import cleanup_uploads_job

    try:
        queue = get_queue()
        enqueue_in = getattr(queue, "enqueue_in", None)
        if callable(enqueue_in):
            enqueue_in(timedelta(seconds=settings.upload_session_ttl_seconds), cleanup_uploads_job)
        else:
            queue.enqueue(cleanup_uploads_job)
    except Exception:
        return


def _discard_files(data: dict[str, Any]) -> None:
    upload_id = str(data.get("upload_id") or "")
    if upload_id:
        shutil.rmtree(storage_root() / "uploads" / upload_id, ignore_errors=True)
        delete_session(upload_id)


class UploadService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_upload(
        self,
        user_id: uuid.UUID,
        file: UploadFile,
        meta_raw: str | None,
        cover: UploadFile | None,
    ) -> UploadCreateResponse:
        try:
            form_meta = _parse_meta(meta_raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc

        extension = _extension(file.filename)
        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported audio format",
            )

        upload_id = uuid.uuid4()
        directory = storage_root() / "uploads" / str(upload_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"audio.{extension}"
        try:
            digest, size = await _write_limited(
                file, target, settings.upload_max_bytes, "File exceeds 50 MB"
            )
        except HTTPException:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        if size == 0:
            shutil.rmtree(directory, ignore_errors=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

        probe = await asyncio.to_thread(probe_audio, target)
        parsed = probe.meta
        if form_meta.model_fields_set:
            parsed = ParsedMeta.model_validate(
                overlay_meta(parsed, form_meta).model_dump()
                | {
                    "isrc": parsed.isrc,
                    "duration_seconds": parsed.duration_seconds,
                    "has_cover": parsed.has_cover,
                }
            )

        embedded_cover = None
        if probe.cover_bytes and len(probe.cover_bytes) <= settings.upload_cover_max_bytes:
            cover_ext = probe.cover_extension or "jpg"
            cover_path = directory / f"embedded.{cover_ext}"
            cover_path.write_bytes(probe.cover_bytes)
            embedded_cover = str(cover_path.relative_to(storage_root()))

        user_cover = None
        if cover is not None and cover.filename:
            cover_ext = _extension(cover.filename)
            if cover_ext == "jpeg":
                cover_ext = "jpg"
            if cover_ext not in ALLOWED_COVER_EXTENSIONS:
                shutil.rmtree(directory, ignore_errors=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported cover format"
                )
            cover_target = directory / f"cover.{cover_ext}"
            try:
                await _write_limited(
                    cover,
                    cover_target,
                    settings.upload_cover_max_bytes,
                    "Cover exceeds 5 MB",
                )
            except HTTPException:
                shutil.rmtree(directory, ignore_errors=True)
                raise
            user_cover = str(cover_target.relative_to(storage_root()))
            parsed.has_cover = True

        data: dict[str, Any] = {
            "upload_id": str(upload_id),
            "user_id": str(user_id),
            "relative_path": str(target.relative_to(storage_root())),
            "original_filename": Path(file.filename or f"audio.{extension}").name,
            "sha256": digest,
            "extension": extension,
            "size": size,
            "duration_seconds": probe.duration_seconds,
            "bitrate": probe.bitrate,
            "sample_rate": probe.sample_rate,
            "isrc": parsed.isrc,
            "original_tags": probe.original_tags,
            "parsed_meta": parsed.model_dump(mode="json"),
            "meta": (
                overlay_meta(parsed, form_meta).model_dump(mode="json")
                if form_meta.model_fields_set
                else parsed.model_dump(mode="json")
            ),
            "embedded_cover": embedded_cover,
            "user_cover": user_cover,
            "fingerprint": None,
            "fingerprint_raw": [],
            "verification": None,
        }
        try:
            save_session(data)
        except Exception as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Upload store unavailable",
            ) from exc
        _schedule_cleanup()
        return UploadCreateResponse(
            upload_id=upload_id, parsed_meta=parsed, verification_pending=True
        )

    async def verify(
        self,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        meta_raw: str | None,
    ) -> VerificationResult:
        data = self._owned_session(user_id, upload_id)
        try:
            form = _parse_meta(meta_raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        parsed = UploadMeta.model_validate(data.get("parsed_meta") or {})
        meta = (
            overlay_meta(parsed, form)
            if meta_raw
            else UploadMeta.model_validate(data.get("meta") or parsed.model_dump())
        )
        await asyncio.to_thread(_ensure_fingerprint, data)
        query = _query(meta)
        cached = load_verification_cache(str(data["sha256"]), query)
        if cached is not None:
            result = VerificationResult.model_validate(cached)
        else:
            result = await asyncio.to_thread(build_verification, data, meta)
            save_verification_cache(str(data["sha256"]), query, result.model_dump(mode="json"))
        data["meta"] = meta.model_dump(mode="json")
        data["verification"] = result.model_dump(mode="json")
        save_session(data)
        return result

    async def confirm(
        self,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        payload: ConfirmUploadRequest,
    ) -> ConfirmUploadResponse:
        data = self._owned_session(user_id, upload_id)
        parsed = UploadMeta.model_validate(data.get("parsed_meta") or {})
        meta = overlay_meta(parsed, payload.meta)
        stored = data.get("verification")
        if not isinstance(stored, dict):
            result = await self.verify(user_id, upload_id, payload.meta.model_dump_json())
            data = self._owned_session(user_id, upload_id)
        else:
            result = VerificationResult.model_validate(stored)
        if payload.accept_suggestions:
            meta = _apply_suggestions(meta, result)
        if not meta.title or not meta.artists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title and artist are required",
            )
        if result.trust_level == "low" and not payload.force:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Low trust: set force=true to publish",
            )

        recording_mbid = result.recording_mbid if result.trust_level in {"high", "medium"} else None
        existing = await self._find_duplicate(str(data["sha256"]), recording_mbid)
        accepted, rejected = await self._check_sources(data, result, payload)
        if existing is not None:
            await self._add_sources(existing, data, accepted, include_user_upload=False)
            if accepted and (not existing.source_kind or existing.source_kind == "user_upload"):
                primary = accepted[0][0]
                existing.source_kind = primary.kind
                existing.source_url = primary.url
                existing.source_id = primary.source_id
            await self._session.commit()
            _discard_files(data)
            return ConfirmUploadResponse(
                track_id=existing.id,
                already_exists=True,
                rejected_source_ids=rejected,
            )

        track = await self._create_track(user_id, data, meta, result, accepted, recording_mbid)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raced = await self._find_duplicate(str(data["sha256"]), recording_mbid)
            if raced is None:
                raise
            _discard_files(data)
            return ConfirmUploadResponse(
                track_id=raced.id, already_exists=True, rejected_source_ids=rejected
            )
        _discard_files(data)
        return ConfirmUploadResponse(
            track_id=track.id,
            already_exists=False,
            rejected_source_ids=rejected,
        )

    def _owned_session(self, user_id: uuid.UUID, upload_id: uuid.UUID) -> dict[str, Any]:
        try:
            data = load_session(str(upload_id))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Upload store unavailable",
            ) from exc
        if data is None or str(data.get("user_id")) != str(user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
        return data

    async def _find_duplicate(self, sha256: str, recording_mbid: str | None) -> Track | None:
        by_sha = await self._session.scalar(select(Track).where(Track.audio_sha256 == sha256))
        if isinstance(by_sha, Track):
            return by_sha
        if not recording_mbid:
            return None
        by_mbid = await self._session.scalar(select(Track).where(Track.mbid == recording_mbid))
        if isinstance(by_mbid, Track):
            return by_mbid
        return None

    async def _check_sources(
        self,
        data: dict[str, Any],
        result: VerificationResult,
        payload: ConfirmUploadRequest,
    ) -> tuple[list[tuple[Any, int]], list[str]]:
        by_key = {candidate.key: candidate for candidate in result.candidate_sources}
        unknown = [item for item in payload.selected_source_ids if item not in by_key]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown source: {unknown[0]}",
            )
        ordered: list[str] = []
        if payload.primary_source_id and payload.primary_source_id in payload.selected_source_ids:
            ordered.append(payload.primary_source_id)
        for item in payload.selected_source_ids:
            if item not in ordered:
                ordered.append(item)
        raw_values = data.get("fingerprint_raw")
        local_raw = [int(item) for item in raw_values] if isinstance(raw_values, list) else []
        work = storage_root() / "tmp" / f"upload-check-{data['upload_id']}"
        accepted: list[tuple[Any, int]] = []
        rejected: list[str] = []
        try:
            for key in ordered:
                candidate = by_key[key]
                ok = await asyncio.to_thread(source_fingerprint_ok, local_raw, candidate.url, work)
                if not ok:
                    rejected.append(key)
                    continue
                priority = _PRIMARY_PRIORITY if not accepted else _BACKUP_PRIORITY
                accepted.append((candidate, priority))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        return accepted, rejected

    async def _add_sources(
        self,
        track: Track,
        data: dict[str, Any],
        accepted: list[tuple[Any, int]],
        *,
        include_user_upload: bool,
    ) -> None:
        existing = list(
            (
                await self._session.scalars(
                    select(TrackSource).where(TrackSource.track_id == track.id)
                )
            ).all()
        )
        known = {(item.source_kind, item.source_id) for item in existing}
        for candidate, priority in accepted:
            if (candidate.kind, candidate.source_id) in known:
                continue
            self._session.add(
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
            known.add((candidate.kind, candidate.source_id))
        if (
            include_user_upload
            and ("user_upload", None) not in known
            and not any(item.source_kind == "user_upload" for item in existing)
        ):
            self._session.add(
                build_track_source(
                    track_id=track.id,
                    source_kind="user_upload",
                    added_by_user_id=track.added_by_user_id,
                    original_filename=str(data.get("original_filename") or ""),
                    original_tags=(
                        data.get("original_tags")
                        if isinstance(data.get("original_tags"), dict)
                        else {}
                    ),
                    recovery_priority=_USER_UPLOAD_PRIORITY,
                    last_status="ok",
                )
            )

    async def _create_track(
        self,
        user_id: uuid.UUID,
        data: dict[str, Any],
        meta: UploadMeta,
        result: VerificationResult,
        accepted: list[tuple[Any, int]],
        recording_mbid: str | None,
    ) -> Track:
        artists = await self._create_artists(meta.artists)
        resolution = result.album_resolution
        applied = _applied_resolution(meta, resolution)

        unresolved = applied.unresolved if applied is not None else False
        is_single = bool(applied and applied.is_single)
        album_title = (
            applied.title if applied is not None else (meta.album or meta.title or "Unknown")
        )
        album = await self._get_or_create_album(
            title=album_title,
            artist_id=artists[0][0].id,
            release_year=applied.release_year if applied and applied.release_year else meta.year,
            release_group_mbid=applied.release_group_mbid if applied else None,
            is_single=is_single,
            cover_url=applied.cover_url if applied else None,
            data=data,
        )
        source = accepted[0][0] if accepted else None
        metadata: dict[str, Any] = {}
        if result.trust_level == "none":
            metadata["unverified"] = True
        if unresolved:
            metadata["album_unresolved"] = True
        if (
            applied is None
            and resolution is not None
            and not resolution.unresolved
            and meta.album
            and resolution.title.casefold() != meta.album.casefold()
        ):
            metadata["album_suggestion"] = resolution.model_dump(mode="json")

        track = Track(
            title=meta.title or "Unknown",
            album_id=album.id,
            duration_seconds=(
                data.get("duration_seconds")
                if isinstance(data.get("duration_seconds"), int)
                else None
            ),
            file_path="pending",
            status=TrackStatus.ready,
            source_kind=source.kind if source is not None else "user_upload",
            source_url=source.url if source is not None else None,
            source_id=source.source_id if source is not None else None,
            mbid=recording_mbid,
            isrc=data.get("isrc") if isinstance(data.get("isrc"), str) else None,
            has_lyrics=(
                False
                if meta.instrumental
                else (True if meta.has_lyrics is None else meta.has_lyrics)
            ),
            added_by_user_id=user_id,
            acoustid_fingerprint=(
                data.get("fingerprint") if isinstance(data.get("fingerprint"), str) else None
            ),
            cover_url_origin=applied.cover_url if applied and applied.cover_url else None,
            metadata_=metadata,
        )
        self._session.add(track)
        await self._session.flush()
        relative, extension, size, digest = copy_track_file(
            storage_root() / str(data["relative_path"]),
            track.id,
        )
        track.file_path = relative
        track.file_format = extension
        track.file_size_bytes = size
        track.audio_sha256 = digest
        for position, (artist, role) in enumerate(artists):
            self._session.add(
                TrackArtist(track_id=track.id, artist_id=artist.id, role=role, position=position)
            )
        await self._attach_genres(track.id, meta.genres)
        await self._attach_language(track.id, meta.language)
        await self._add_sources(track, data, accepted, include_user_upload=True)
        return track

    async def _create_artists(self, artists: list[ArtistInput]) -> list[tuple[Artist, ArtistRole]]:
        created: list[tuple[Artist, ArtistRole]] = []
        for item in artists:
            artist = await get_or_create_artist(self._session, item.name)
            created.append((artist, ArtistRole(item.role)))
        return created

    async def _get_or_create_album(
        self,
        *,
        title: str,
        artist_id: uuid.UUID,
        release_year: int | None,
        release_group_mbid: str | None,
        is_single: bool,
        cover_url: str | None,
        data: dict[str, Any],
    ) -> Album:
        if release_group_mbid:
            existing = await self._session.scalar(
                select(Album).where(Album.mbid == release_group_mbid)
            )
            if existing is not None:
                return existing
        album = Album(
            title=title,
            primary_artist_id=artist_id,
            mbid=release_group_mbid,
            release_year=release_year,
            is_single=is_single,
        )
        cover_rel = data.get("user_cover") or data.get("embedded_cover")
        if isinstance(cover_rel, str):
            album.cover_path = save_cover_file(uuid.uuid4(), storage_root() / cover_rel)
        elif cover_url:
            album.metadata_ = {"cover_url": cover_url}
        self._session.add(album)
        await self._session.flush()
        return album

    async def _attach_genres(self, track_id: uuid.UUID, genres: list[str]) -> None:
        for name in genres:
            slug = _slugify(name)
            genre = await self._session.scalar(select(Genre).where(Genre.slug == slug))
            if genre is None:
                genre = Genre(name=name, slug=slug)
                self._session.add(genre)
                await self._session.flush()
            await self._session.merge(TrackGenre(track_id=track_id, genre_id=genre.id, weight=1.0))

    async def _attach_language(self, track_id: uuid.UUID, language: str | None) -> None:
        if not language:
            return
        code = language.strip().lower()
        row = await self._session.scalar(select(Language).where(Language.code == code))
        if row is None:
            return
        await self._session.merge(TrackLanguage(track_id=track_id, language_id=row.id))


def _parse_meta(raw: str | None) -> UploadMeta:
    from pydantic import ValidationError

    try:
        return _parse_upload_meta(raw)
    except ValidationError as exc:
        raise ValueError("Invalid meta") from exc


def _parse_upload_meta(raw: str | None) -> UploadMeta:
    from app.schemas.upload import parse_upload_meta

    return parse_upload_meta(raw)


def _apply_suggestions(meta: UploadMeta, result: VerificationResult) -> UploadMeta:
    suggestion = result.suggestions
    artists = meta.artists
    if suggestion.artist:
        artists = [ArtistInput(name=suggestion.artist, role="main")]
    return meta.model_copy(
        update={
            "title": suggestion.title or meta.title,
            "artists": artists,
            "album": suggestion.album if suggestion.album else meta.album,
            "year": suggestion.year if suggestion.year is not None else meta.year,
            "genres": suggestion.genres or meta.genres,
        }
    )


def _applied_resolution(
    meta: UploadMeta, resolution: AlbumResolution | None
) -> AlbumResolution | None:
    if resolution is None:
        return None
    if not meta.album:
        return resolution
    if not resolution.unresolved and resolution.title.casefold() == meta.album.casefold():
        return resolution
    return None


async def _write_limited(
    upload: UploadFile, target: Path, limit: int, message: str
) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with target.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=message
                )
            hasher.update(chunk)
            handle.write(chunk)
    return hasher.hexdigest(), size
