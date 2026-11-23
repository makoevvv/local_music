from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import tarfile
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.storage import copy_track_file, resolve_track_file, storage_root
from app.models.catalog import (
    Album,
    Artist,
    ArtistRole,
    Genre,
    Language,
    Play,
    Playlist,
    PlaylistTrack,
    Track,
    TrackArtist,
    TrackGenre,
    TrackLanguage,
    TrackSource,
    TrackStatus,
)
from app.models.user import User, UserRole
from app.services.track_sources import build_track_source, normalize_source_kind
from app.services.ytdlp import download_audio, search_entries

SCHEMA_VERSION = "1.0"
ImportMode = Literal["skip-existing", "overwrite", "mirror"]


def exports_root() -> Path:
    root = Path(settings.exports_local_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_uuid(raw: str | uuid.UUID) -> uuid.UUID:
    return raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))


@dataclass
class ExportOptions:
    out: Path
    minimal: bool = False
    include_covers: bool = False
    include_secrets: bool = False
    no_plays: bool = False


@dataclass
class ExportResult:
    path: Path
    track_count: int
    sha256: str
    manifest: dict[str, Any]


@dataclass
class ImportResult:
    imported_tracks: int = 0
    skipped_tracks: int = 0
    overwritten_tracks: int = 0
    sha256_mapped: int = 0
    warnings: list[str] = field(default_factory=list)
    id_map: dict[str, str] = field(default_factory=dict)


@dataclass
class RestoreResult:
    attempted: int = 0
    restored: int = 0
    unrecoverable: int = 0
    skipped: int = 0
    dry_run: bool = False
    details: list[dict[str, Any]] = field(default_factory=list)


class LibraryIndexService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def export_index(self, options: ExportOptions) -> ExportResult:
        tracks = (
            await self._session.scalars(
                select(Track)
                .options(
                    selectinload(Track.artists).selectinload(TrackArtist.artist),
                    selectinload(Track.album),
                    selectinload(Track.sources),
                )
                .order_by(Track.created_at.asc())
            )
        ).all()

        track_rows: list[dict[str, Any]] = []
        for track in tracks:
            track_rows.append(await self._serialize_track(track))

        users = (await self._session.scalars(select(User).order_by(User.created_at.asc()))).all()
        playlists = (
            await self._session.scalars(
                select(Playlist)
                .options(selectinload(Playlist.tracks))
                .order_by(Playlist.created_at.asc())
            )
        ).all()

        with tempfile.TemporaryDirectory(prefix="library-export-") as tmp:
            tmp_path = Path(tmp)
            tracks_path = tmp_path / "tracks.jsonl"
            with tracks_path.open("w", encoding="utf-8") as handle:
                for track_row in track_rows:
                    handle.write(json.dumps(track_row, ensure_ascii=False) + "\n")

            tracks_sha = hashlib.sha256(tracks_path.read_bytes()).hexdigest()
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "exported_at": _iso(datetime.now(UTC)),
                "track_count": len(track_rows),
                "artist_count": await self._session.scalar(
                    select(func.count()).select_from(Artist)
                ),
                "album_count": await self._session.scalar(select(func.count()).select_from(Album)),
                "tracks_sha256": tracks_sha,
                "minimal": options.minimal,
                "include_covers": options.include_covers and not options.minimal,
                "include_secrets": options.include_secrets,
                "include_plays": not options.no_plays and not options.minimal,
            }
            (tmp_path / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            if not options.minimal:
                users_path = tmp_path / "users.jsonl"
                with users_path.open("w", encoding="utf-8") as handle:
                    for user in users:
                        user_row: dict[str, Any] = {
                            "id": str(user.id),
                            "email": user.email,
                            "username": user.username,
                            "role": user.role.value,
                            "is_master": user.is_master,
                            "is_active": user.is_active,
                            "created_at": _iso(user.created_at),
                        }
                        if options.include_secrets:
                            user_row["password_hash"] = user.password_hash
                        handle.write(json.dumps(user_row, ensure_ascii=False) + "\n")

                playlists_path = tmp_path / "playlists.jsonl"
                with playlists_path.open("w", encoding="utf-8") as handle:
                    for playlist in playlists:
                        playlist_row = {
                            "id": str(playlist.id),
                            "owner_id": str(playlist.owner_id),
                            "name": playlist.name,
                            "is_favourite": playlist.is_favourite,
                            "is_public": playlist.is_public,
                            "cover_path": playlist.cover_path,
                            "created_at": _iso(playlist.created_at),
                            "tracks": [
                                {
                                    "track_id": str(link.track_id),
                                    "position": link.position,
                                    "added_at": _iso(link.added_at),
                                }
                                for link in sorted(playlist.tracks, key=lambda item: item.position)
                            ],
                        }
                        handle.write(json.dumps(playlist_row, ensure_ascii=False) + "\n")

                if not options.no_plays:
                    plays = (
                        await self._session.scalars(select(Play).order_by(Play.id.asc()))
                    ).all()
                    plays_path = tmp_path / "plays.jsonl"
                    with plays_path.open("w", encoding="utf-8") as handle:
                        for play in plays:
                            handle.write(
                                json.dumps(
                                    {
                                        "id": play.id,
                                        "user_id": str(play.user_id),
                                        "track_id": str(play.track_id),
                                        "started_at": _iso(play.started_at),
                                        "listened_seconds": play.listened_seconds,
                                        "completed": play.completed,
                                        "source": play.source,
                                    },
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )

                if options.include_covers:
                    covers_dir = tmp_path / "covers"
                    covers_dir.mkdir(exist_ok=True)
                    for track in tracks:
                        if track.album and track.album.cover_path:
                            try:
                                src = (
                                    Path(track.album.cover_path)
                                    if Path(track.album.cover_path).is_absolute()
                                    else storage_root() / track.album.cover_path
                                )
                                if src.is_file():
                                    dest = covers_dir / f"{track.album.id}{src.suffix or '.jpg'}"
                                    shutil.copy2(src, dest)
                            except OSError:
                                continue

            options.out.parent.mkdir(parents=True, exist_ok=True)
            if options.minimal:
                # Single gzipped jsonl (+ tiny manifest sidecar inside gzip as first comment? use tar of two files still)
                # Spec: library.jsonl.gz — pack tracks.jsonl gzipped; also write companion manifest next to it.
                with gzip.open(options.out, "wt", encoding="utf-8") as gz:
                    for row in track_rows:
                        gz.write(json.dumps(row, ensure_ascii=False) + "\n")
                manifest_sidecar = options.out.with_suffix(options.out.suffix + ".manifest.json")
                if options.out.name.endswith(".jsonl.gz"):
                    manifest_sidecar = Path(
                        str(options.out)[: -len(".jsonl.gz")] + ".manifest.json"
                    )
                manifest_sidecar.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            else:
                with tarfile.open(options.out, "w:gz") as tar:
                    for path in sorted(tmp_path.rglob("*")):
                        if path.is_file():
                            tar.add(path, arcname=path.relative_to(tmp_path).as_posix())

        return ExportResult(
            path=options.out,
            track_count=len(track_rows),
            sha256=tracks_sha,
            manifest=manifest,
        )

    async def _serialize_track(self, track: Track) -> dict[str, Any]:
        genres = (
            await self._session.scalars(
                select(Genre)
                .join(TrackGenre, TrackGenre.genre_id == Genre.id)
                .where(TrackGenre.track_id == track.id)
            )
        ).all()
        languages = (
            await self._session.scalars(
                select(Language)
                .join(TrackLanguage, TrackLanguage.language_id == Language.id)
                .where(TrackLanguage.track_id == track.id)
            )
        ).all()

        album_payload = None
        if track.album is not None:
            album_payload = {
                "id": str(track.album.id),
                "title": track.album.title,
                "mbid": track.album.mbid,
                "is_single": track.album.is_single,
                "release_year": track.album.release_year,
                "cover_path": track.album.cover_path,
            }

        artists_payload = []
        for link in sorted(track.artists, key=lambda item: item.position):
            if link.artist is None:
                continue
            artists_payload.append(
                {
                    "id": str(link.artist.id),
                    "name": link.artist.name,
                    "role": link.role.value,
                    "mbid": link.artist.mbid,
                    "position": link.position,
                }
            )

        # Fallback: denormalized source if track_sources empty (pre-4.2 leftovers).
        sources = list(track.sources)
        if not sources and (track.source_kind or track.source_url or track.source_id):
            sources = [
                build_track_source(
                    track_id=track.id,
                    source_kind=track.source_kind,
                    source_url=track.source_url,
                    source_id=track.source_id,
                    added_by_user_id=track.added_by_user_id,
                    last_status="ok" if track.status == TrackStatus.ready else None,
                )
            ]

        return {
            "id": str(track.id),
            "title": track.title,
            "artists": artists_payload,
            "album": album_payload,
            "genres": [genre.slug for genre in genres],
            "languages": [language.code for language in languages],
            "duration": track.duration_seconds,
            "audio_sha256": track.audio_sha256,
            "mbid": track.mbid,
            "isrc": track.isrc,
            "acoustid_fingerprint": track.acoustid_fingerprint,
            "cover_url_origin": track.cover_url_origin,
            "file_format": track.file_format,
            "status": track.status.value,
            "explicit": track.explicit,
            "has_lyrics": track.has_lyrics,
            "added_by_user_id": str(track.added_by_user_id) if track.added_by_user_id else None,
            "created_at": _iso(track.created_at),
            "sources": [
                {
                    "id": str(source.id) if getattr(source, "id", None) else None,
                    "kind": source.source_kind,
                    "url": source.source_url,
                    "source_id": source.source_id,
                    "original_filename": source.original_filename,
                    "original_tags": source.original_tags or {},
                    "added_by_user_id": (
                        str(source.added_by_user_id) if source.added_by_user_id else None
                    ),
                    "added_at": _iso(source.added_at) if source.added_at else None,
                    "recovery_priority": source.recovery_priority,
                    "last_status": source.last_status,
                    "last_checked_at": _iso(source.last_checked_at),
                }
                for source in sources
            ],
        }

    async def import_index(self, archive: Path, *, mode: ImportMode) -> ImportResult:
        if not archive.exists():
            raise FileNotFoundError(f"Archive not found: {archive}")

        result = ImportResult()
        with tempfile.TemporaryDirectory(prefix="library-import-") as tmp:
            tmp_path = Path(tmp)
            track_rows = self._extract_tracks(archive, tmp_path)
            users_path = tmp_path / "users.jsonl"
            playlists_path = tmp_path / "playlists.jsonl"
            plays_path = tmp_path / "plays.jsonl"

            if users_path.exists():
                await self._import_users(users_path, mode=mode, result=result)

            for row in track_rows:
                await self._import_track_row(row, mode=mode, result=result)

            if playlists_path.exists():
                await self._import_playlists(playlists_path, mode=mode, result=result)

            if plays_path.exists() and mode != "skip-existing":
                await self._import_plays(plays_path, result=result)

            if mode == "mirror":
                dump_ids = {_parse_uuid(row["id"]) for row in track_rows}
                local_ids = set(await self._session.scalars(select(Track.id)))
                extras = local_ids - dump_ids
                if extras:
                    result.warnings.append(
                        f"mirror: {len(extras)} local track(s) not in dump (left untouched)"
                    )

            await self._session.commit()
        return result

    def _extract_tracks(self, archive: Path, tmp_path: Path) -> list[dict[str, Any]]:
        name = archive.name
        if name.endswith(".tar.gz") or name.endswith(".tgz"):
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(tmp_path, filter="data")
            tracks_path = tmp_path / "tracks.jsonl"
            if not tracks_path.exists():
                raise ValueError("Archive missing tracks.jsonl")
            return [
                json.loads(line)
                for line in tracks_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        if name.endswith(".jsonl.gz") or name.endswith(".gz"):
            with gzip.open(archive, "rt", encoding="utf-8") as handle:
                return [json.loads(line) for line in handle if line.strip()]

        if name.endswith(".jsonl"):
            return [
                json.loads(line)
                for line in archive.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        raise ValueError(f"Unsupported archive format: {archive}")

    async def _import_users(self, path: Path, *, mode: ImportMode, result: ImportResult) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            user_id = _parse_uuid(row["id"])
            existing = await self._session.get(User, user_id)
            if existing is not None:
                if mode == "skip-existing":
                    continue
                existing.email = row["email"]
                existing.username = row["username"]
                existing.role = UserRole(row.get("role", "user"))
                existing.is_active = bool(row.get("is_active", True))
                if row.get("password_hash"):
                    existing.password_hash = row["password_hash"]
                continue
            by_email = await self._session.scalar(select(User).where(User.email == row["email"]))
            if by_email is not None:
                result.warnings.append(f"user email conflict for {row['email']}, skipped")
                continue
            password_hash = row.get("password_hash") or "!"
            want_master = bool(row.get("is_master", False))
            if want_master:
                existing_master = await self._session.scalar(
                    select(User).where(User.is_master.is_(True))
                )
                if existing_master is not None and existing_master.id != user_id:
                    want_master = False
                    result.warnings.append(
                        f"user {row['email']}: master already exists, imported as non-master"
                    )
            user = User(
                id=user_id,
                email=row["email"],
                username=row["username"],
                password_hash=password_hash,
                role=UserRole(row.get("role", "user")),
                is_master=want_master,
                is_active=bool(row.get("is_active", True)),
            )
            self._session.add(user)
        await self._session.flush()

    async def _import_track_row(
        self, row: dict[str, Any], *, mode: ImportMode, result: ImportResult
    ) -> None:
        track_id = _parse_uuid(row["id"])
        audio_sha = row.get("audio_sha256")

        existing_by_id = await self._session.get(Track, track_id)
        if existing_by_id is not None:
            if mode == "skip-existing":
                result.skipped_tracks += 1
                result.id_map[str(track_id)] = str(existing_by_id.id)
                return
            if (
                audio_sha
                and existing_by_id.audio_sha256
                and existing_by_id.audio_sha256 != audio_sha
            ):
                result.warnings.append(
                    f"UUID conflict for {track_id}: different audio_sha256, skipped"
                )
                result.skipped_tracks += 1
                return
            await self._apply_track_row(existing_by_id, row, create_sources=True)
            result.overwritten_tracks += 1
            result.id_map[str(track_id)] = str(existing_by_id.id)
            return

        if audio_sha:
            existing_by_sha = await self._session.scalar(
                select(Track).where(Track.audio_sha256 == audio_sha)
            )
            if existing_by_sha is not None:
                result.sha256_mapped += 1
                result.skipped_tracks += 1
                result.id_map[str(track_id)] = str(existing_by_sha.id)
                result.warnings.append(
                    f"sha256 conflict: imported {track_id} → existing {existing_by_sha.id}"
                )
                # Merge sources onto existing track.
                await self._merge_sources(existing_by_sha.id, row.get("sources") or [])
                return

        track = Track(
            id=track_id,
            title=row.get("title") or "Unknown Track",
            file_path="pending",
            status=TrackStatus.ready if row.get("status") == "ready" else TrackStatus.failed,
            audio_sha256=audio_sha,
            mbid=row.get("mbid"),
            isrc=row.get("isrc"),
            acoustid_fingerprint=row.get("acoustid_fingerprint"),
            cover_url_origin=row.get("cover_url_origin"),
            duration_seconds=row.get("duration"),
            file_format=row.get("file_format"),
            explicit=bool(row.get("explicit", False)),
            has_lyrics=bool(row.get("has_lyrics", True)),
            added_by_user_id=(
                _parse_uuid(row["added_by_user_id"]) if row.get("added_by_user_id") else None
            ),
        )
        # Mark missing file until restore.
        if track.status == TrackStatus.ready:
            track.metadata_ = {"missing_file": True}
        self._session.add(track)
        await self._session.flush()
        await self._apply_track_row(track, row, create_sources=True)
        result.imported_tracks += 1
        result.id_map[str(track_id)] = str(track.id)

    async def _apply_track_row(
        self, track: Track, row: dict[str, Any], *, create_sources: bool
    ) -> None:
        track.title = row.get("title") or track.title
        track.duration_seconds = row.get("duration")
        track.mbid = row.get("mbid")
        track.isrc = row.get("isrc")
        track.acoustid_fingerprint = row.get("acoustid_fingerprint")
        track.cover_url_origin = row.get("cover_url_origin")
        track.file_format = row.get("file_format") or track.file_format
        track.explicit = bool(row.get("explicit", False))
        track.has_lyrics = bool(row.get("has_lyrics", True))
        if row.get("audio_sha256") and not track.audio_sha256:
            track.audio_sha256 = row["audio_sha256"]

        album_row = row.get("album")
        if album_row and album_row.get("title"):
            album_id = _parse_uuid(album_row["id"]) if album_row.get("id") else uuid.uuid4()
            album = await self._session.get(Album, album_id)
            if album is None:
                album = Album(
                    id=album_id,
                    title=album_row["title"],
                    mbid=album_row.get("mbid"),
                    is_single=bool(album_row.get("is_single", False)),
                    release_year=album_row.get("release_year"),
                    cover_path=album_row.get("cover_path"),
                )
                self._session.add(album)
                await self._session.flush()
            track.album_id = album.id

        for artist_row in row.get("artists") or []:
            artist_id = _parse_uuid(artist_row["id"]) if artist_row.get("id") else uuid.uuid4()
            artist = await self._session.get(Artist, artist_id)
            if artist is None:
                artist = Artist(
                    id=artist_id,
                    name=artist_row.get("name") or "Unknown Artist",
                    mbid=artist_row.get("mbid"),
                    sort_name=artist_row.get("name"),
                )
                self._session.add(artist)
                await self._session.flush()
            link = await self._session.get(
                TrackArtist,
                {
                    "track_id": track.id,
                    "artist_id": artist.id,
                    "role": ArtistRole(artist_row.get("role", "main")),
                },
            )
            if link is None:
                self._session.add(
                    TrackArtist(
                        track_id=track.id,
                        artist_id=artist.id,
                        role=ArtistRole(artist_row.get("role", "main")),
                        position=int(artist_row.get("position") or 0),
                    )
                )

        for slug in row.get("genres") or []:
            genre = await self._session.scalar(select(Genre).where(Genre.slug == slug))
            if genre is None:
                genre = Genre(name=slug, slug=slug)
                self._session.add(genre)
                await self._session.flush()
            existing_genre = await self._session.scalar(
                select(TrackGenre).where(
                    TrackGenre.track_id == track.id,
                    TrackGenre.genre_id == genre.id,
                )
            )
            if existing_genre is None:
                self._session.add(TrackGenre(track_id=track.id, genre_id=genre.id))

        for code in row.get("languages") or []:
            language = await self._session.scalar(select(Language).where(Language.code == code))
            if language is None:
                language = Language(code=code, name=code)
                self._session.add(language)
                await self._session.flush()
            existing_language = await self._session.scalar(
                select(TrackLanguage).where(
                    TrackLanguage.track_id == track.id,
                    TrackLanguage.language_id == language.id,
                )
            )
            if existing_language is None:
                self._session.add(TrackLanguage(track_id=track.id, language_id=language.id))

        primary = None
        for source_row in row.get("sources") or []:
            if primary is None:
                primary = source_row
            if create_sources:
                await self._ensure_source(track.id, source_row)

        if primary:
            track.source_kind = normalize_source_kind(
                primary.get("kind") or primary.get("source_kind")
            )
            track.source_url = primary.get("url") or primary.get("source_url")
            track.source_id = primary.get("source_id")

        track.updated_at = datetime.now(UTC)
        await self._session.flush()

    async def _ensure_source(self, track_id: uuid.UUID, source_row: dict[str, Any]) -> None:
        kind = normalize_source_kind(source_row.get("kind") or source_row.get("source_kind"))
        source_id = source_row.get("source_id")
        source_url = source_row.get("url") or source_row.get("source_url")
        stmt = select(TrackSource).where(
            TrackSource.track_id == track_id,
            TrackSource.source_kind == kind,
        )
        if source_id:
            stmt = stmt.where(TrackSource.source_id == source_id)
        elif source_url:
            stmt = stmt.where(TrackSource.source_url == source_url)
        existing = await self._session.scalar(stmt)
        if existing is not None:
            return
        source = build_track_source(
            track_id=track_id,
            source_kind=kind,
            source_url=source_url,
            source_id=source_id,
            added_by_user_id=(
                _parse_uuid(source_row["added_by_user_id"])
                if source_row.get("added_by_user_id")
                else None
            ),
            original_filename=source_row.get("original_filename"),
            original_tags=source_row.get("original_tags") or {},
            last_status=source_row.get("last_status"),
            recovery_priority=source_row.get("recovery_priority"),
        )
        self._session.add(source)

    async def _merge_sources(self, track_id: uuid.UUID, sources: list[dict[str, Any]]) -> None:
        for source_row in sources:
            await self._ensure_source(track_id, source_row)

    async def _import_playlists(
        self, path: Path, *, mode: ImportMode, result: ImportResult
    ) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            playlist_id = _parse_uuid(row["id"])
            existing = await self._session.get(Playlist, playlist_id)
            if existing is not None and mode == "skip-existing":
                continue
            if existing is None:
                owner_id = _parse_uuid(row["owner_id"])
                if await self._session.get(User, owner_id) is None:
                    result.warnings.append(
                        f"playlist {playlist_id}: owner {owner_id} missing, skipped"
                    )
                    continue
                existing = Playlist(
                    id=playlist_id,
                    owner_id=owner_id,
                    name=row.get("name") or "Playlist",
                    is_favourite=bool(row.get("is_favourite", False)),
                    is_public=bool(row.get("is_public", False)),
                    cover_path=row.get("cover_path"),
                )
                self._session.add(existing)
                await self._session.flush()
            else:
                existing.name = row.get("name") or existing.name
                existing.is_public = bool(row.get("is_public", existing.is_public))

            for link_row in row.get("tracks") or []:
                imported_track_id = str(link_row["track_id"])
                mapped = result.id_map.get(imported_track_id, imported_track_id)
                track_uuid = _parse_uuid(mapped)
                if await self._session.get(Track, track_uuid) is None:
                    continue
                link = await self._session.get(
                    PlaylistTrack,
                    {"playlist_id": existing.id, "track_id": track_uuid},
                )
                if link is None:
                    self._session.add(
                        PlaylistTrack(
                            playlist_id=existing.id,
                            track_id=track_uuid,
                            position=int(link_row.get("position") or 0),
                        )
                    )

    async def _import_plays(self, path: Path, result: ImportResult) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            user_id = _parse_uuid(row["user_id"])
            imported_track_id = str(row["track_id"])
            mapped = result.id_map.get(imported_track_id, imported_track_id)
            track_id = _parse_uuid(mapped)
            if await self._session.get(User, user_id) is None:
                continue
            if await self._session.get(Track, track_id) is None:
                continue
            self._session.add(
                Play(
                    user_id=user_id,
                    track_id=track_id,
                    listened_seconds=int(row.get("listened_seconds") or 0),
                    completed=bool(row.get("completed", False)),
                    source=row.get("source"),
                )
            )

    async def library_health(self) -> dict[str, Any]:
        tracks = (await self._session.scalars(select(Track))).all()
        missing_files = 0
        for track in tracks:
            if track.status == TrackStatus.unrecoverable:
                continue
            if await self._track_file_missing(track):
                missing_files += 1

        unrecoverable = await self._session.scalar(
            select(func.count()).select_from(Track).where(Track.status == TrackStatus.unrecoverable)
        )
        sources_by_status_rows = await self._session.execute(
            select(TrackSource.last_status, func.count())
            .group_by(TrackSource.last_status)
            .order_by(TrackSource.last_status)
        )
        sources_by_status = {
            (status or "unknown"): count for status, count in sources_by_status_rows.all()
        }
        stale = await self._session.scalar(
            select(func.count())
            .select_from(TrackSource)
            .where(TrackSource.last_status.in_(("gone", "geo_blocked", "private", "forbidden")))
        )
        return {
            "track_count": len(tracks),
            "missing_files": missing_files,
            "unrecoverable": int(unrecoverable or 0),
            "stale_sources": int(stale or 0),
            "sources_by_status": sources_by_status,
        }

    async def _track_file_missing(self, track: Track) -> bool:
        if track.file_path in {"", "pending"} or track.file_path is None:
            return True
        if track.metadata_ and track.metadata_.get("missing_file"):
            return True
        try:
            resolve_track_file(track.file_path)
            return False
        except FileNotFoundError:
            return True

    async def restore_library(
        self,
        *,
        strategy: str = "best-source-first",
        concurrency: int = 2,
        dry_run: bool = False,
        track_ids: list[uuid.UUID] | None = None,
    ) -> RestoreResult:
        _ = strategy, concurrency  # reserved for parallel restore
        result = RestoreResult(dry_run=dry_run)
        stmt = select(Track).options(
            selectinload(Track.sources),
            selectinload(Track.artists).selectinload(TrackArtist.artist),
        )
        if track_ids:
            stmt = stmt.where(Track.id.in_(track_ids))
        tracks = (await self._session.scalars(stmt)).all()

        for track in tracks:
            if track.status == TrackStatus.downloading:
                result.skipped += 1
                continue
            missing = await self._track_file_missing(track)
            if not missing:
                result.skipped += 1
                continue

            result.attempted += 1
            if dry_run:
                result.details.append(
                    {
                        "track_id": str(track.id),
                        "title": track.title,
                        "sources": len(track.sources),
                        "action": "would_restore",
                    }
                )
                continue

            restored = await self._restore_one_track(track)
            if restored:
                result.restored += 1
                result.details.append(
                    {"track_id": str(track.id), "title": track.title, "action": "restored"}
                )
            else:
                track.status = TrackStatus.unrecoverable
                track.updated_at = datetime.now(UTC)
                result.unrecoverable += 1
                result.details.append(
                    {
                        "track_id": str(track.id),
                        "title": track.title,
                        "action": "unrecoverable",
                    }
                )
            await self._session.commit()

        return result

    async def _restore_one_track(self, track: Track) -> bool:
        sources = sorted(
            track.sources,
            key=lambda source: (
                0 if source.last_status == "ok" else 1,
                source.recovery_priority,
                source.added_at or datetime.min.replace(tzinfo=UTC),
            ),
        )
        for source in sources:
            if source.source_kind in {"user_upload", "upload"}:
                meta = dict(track.metadata_ or {})
                meta["needs_user_reupload"] = True
                track.metadata_ = meta
                continue
            url = source.source_url
            if not url and source.source_kind == "youtube" and source.source_id:
                url = f"https://www.youtube.com/watch?v={source.source_id}"
            if not url:
                continue
            try:
                ok = await self._download_into_track(track, url, expected_sha=track.audio_sha256)
            except Exception:
                source.last_status = "gone"
                source.last_checked_at = datetime.now(UTC)
                continue
            if ok:
                source.last_status = "ok"
                source.last_checked_at = datetime.now(UTC)
                track.source_kind = source.source_kind
                track.source_url = source.source_url
                track.source_id = source.source_id
                return True
            source.last_status = "checksum_mismatch"
            source.last_checked_at = datetime.now(UTC)

        # Fuzzy fallback by artist - title (AcoustID API is stage 4.1; fingerprint kept for later).
        artist_name = None
        for link in sorted(track.artists, key=lambda item: item.position):
            if link.artist is not None:
                artist_name = link.artist.name
                break
        query = f"{artist_name} - {track.title}" if artist_name else track.title
        try:
            results = search_entries(query, limit=3, include_soundcloud=True)
        except Exception:
            results = []
        for candidate in results:
            try:
                ok = await self._download_into_track(
                    track,
                    candidate.source_url,
                    expected_sha=track.audio_sha256,
                    relax_checksum=bool(track.acoustid_fingerprint or not track.audio_sha256),
                )
            except Exception:
                continue
            if ok:
                self._session.add(
                    build_track_source(
                        track_id=track.id,
                        source_kind=candidate.source_kind,
                        source_url=candidate.source_url,
                        source_id=candidate.source_id,
                        tier=candidate.tier,
                        last_status="ok",
                    )
                )
                track.source_kind = candidate.source_kind
                track.source_url = candidate.source_url
                track.source_id = candidate.source_id
                return True
        return False

    async def _download_into_track(
        self,
        track: Track,
        url: str,
        *,
        expected_sha: str | None,
        relax_checksum: bool = False,
    ) -> bool:
        tmp_dir = storage_root() / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(tmp_dir / f"restore-{track.id}.%(ext)s")
        downloaded = Path(download_audio(url, output_template))
        digest = hashlib.sha256(downloaded.read_bytes()).hexdigest()
        if expected_sha and digest != expected_sha and not relax_checksum:
            downloaded.unlink(missing_ok=True)
            return False

        relative, extension, size, file_digest = copy_track_file(downloaded, track.id)
        downloaded.unlink(missing_ok=True)
        track.file_path = relative
        track.file_format = extension
        track.file_size_bytes = size
        if not track.audio_sha256:
            track.audio_sha256 = file_digest
        track.status = TrackStatus.ready
        meta = dict(track.metadata_ or {})
        meta.pop("missing_file", None)
        meta.pop("needs_user_reupload", None)
        track.metadata_ = meta
        track.updated_at = datetime.now(UTC)
        await self._session.flush()
        return True


def list_export_files() -> list[dict[str, Any]]:
    root = exports_root()
    items: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        if not (
            path.name.endswith(".tar.gz")
            or path.name.endswith(".jsonl.gz")
            or path.name.endswith(".tgz")
        ):
            continue
        items.append(
            {
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "modified_at": _iso(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)),
            }
        )
    return items


def resolve_export_file(filename: str) -> Path:
    if "/" in filename or "\\" in filename or filename in {".", ".."}:
        raise ValueError("Invalid filename")
    path = (exports_root() / filename).resolve()
    if not str(path).startswith(str(exports_root().resolve())):
        raise ValueError("Invalid filename")
    if not path.is_file():
        raise FileNotFoundError(filename)
    return path
