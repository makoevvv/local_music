from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import resolve_track_file
from app.models.catalog import (
    Album,
    Artist,
    ArtistRole,
    Genre,
    Language,
    LikeSentiment,
    Playlist,
    Track,
    TrackArtist,
    TrackStatus,
)
from app.models.user import User
from app.repositories.catalog import CatalogRepository, PlaylistRepository
from app.schemas.catalog import (
    AlbumBrief,
    ArtistBrief,
    GenrePublic,
    LanguagePublic,
    LikeRequest,
    PlayHeartbeatRequest,
    PlaylistCreateRequest,
    PlaylistDetail,
    PlaylistReorderRequest,
    PlaylistSummary,
    PlaylistTrackItem,
    PlaylistTracksRequest,
    PlaylistUpdateRequest,
    PlayStartResponse,
    TrackDetail,
    TrackListItem,
    TrackListResponse,
)


def _artist_briefs(track: Track) -> list[ArtistBrief]:
    return [
        ArtistBrief(id=link.artist.id, name=link.artist.name)
        for link in sorted(track.artists, key=lambda item: item.position)
        if link.artist is not None
    ]


def _track_list_item(track: Track, sentiment: LikeSentiment | None = None) -> TrackListItem:
    album = None
    if track.album is not None:
        album = AlbumBrief(
            id=track.album.id,
            title=track.album.title,
            release_year=track.album.release_year,
        )
    return TrackListItem(
        id=track.id,
        title=track.title,
        duration_seconds=track.duration_seconds,
        status=track.status,
        play_count=track.play_count,
        has_lyrics=track.has_lyrics,
        artists=_artist_briefs(track),
        album=album,
        user_sentiment=sentiment,
    )


class CatalogService:
    FAVOURITE_NAME = "Любимое"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._catalog = CatalogRepository(session)
        self._playlists = PlaylistRepository(session)

    async def ensure_favourite_playlist(self, user_id: uuid.UUID) -> Playlist:
        favourite = await self._playlists.get_favourite(user_id)
        if favourite is not None:
            return favourite
        playlist = Playlist(
            owner_id=user_id,
            name=self.FAVOURITE_NAME,
            is_favourite=True,
            is_public=False,
        )
        return await self._playlists.create(playlist)

    async def list_tracks(
        self,
        user: User,
        *,
        q: str | None,
        genre: str | None,
        language: str | None,
        has_lyrics: bool | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> TrackListResponse:
        tracks, total = await self._catalog.list_tracks(
            q=q,
            genre_slug=genre,
            language_code=language,
            has_lyrics=has_lyrics,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        items: list[TrackListItem] = []
        for track in tracks:
            like = await self._catalog.get_user_like(user.id, track.id)
            items.append(_track_list_item(track, like.sentiment if like else None))
        return TrackListResponse(items=items, page=page, page_size=page_size, total=total)

    async def get_track(self, user: User, track_id: uuid.UUID) -> TrackDetail:
        track = await self._catalog.get_track_with_relations(track_id)
        if track is None or track.status not in {TrackStatus.ready, TrackStatus.downloading}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
        like = await self._catalog.get_user_like(user.id, track.id)
        genres = await self._catalog.get_genres_for_track(track.id)
        languages = await self._catalog.get_languages_for_track(track.id)
        base = _track_list_item(track, like.sentiment if like else None)
        return TrackDetail(
            **base.model_dump(),
            file_format=track.file_format,
            explicit=track.explicit,
            genres=[GenrePublic.model_validate(item) for item in genres],
            languages=[LanguagePublic.model_validate(item) for item in languages],
            created_at=track.created_at,
        )

    async def stream_track(self, user: User, track_id: uuid.UUID) -> FileResponse:
        track = await self._catalog.get_track(track_id)
        if track is None or track.status != TrackStatus.ready:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
        try:
            file_path = resolve_track_file(track.file_path)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Track file missing"
            ) from exc
        media_type = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "m4a": "audio/mp4",
        }.get(track.file_format or "mp3", "application/octet-stream")
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=f"{track.title}.{track.file_format or 'mp3'}",
        )

    async def set_like(self, user: User, track_id: uuid.UUID, payload: LikeRequest) -> None:
        track = await self._catalog.get_track(track_id)
        if track is None or track.status != TrackStatus.ready:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
        await self._catalog.set_like(user.id, track_id, payload.sentiment)
        if payload.sentiment == LikeSentiment.like:
            favourite = await self.ensure_favourite_playlist(user.id)
            await self._playlists.add_tracks(favourite.id, [track_id])
        await self._session.commit()

    async def remove_like(self, user: User, track_id: uuid.UUID) -> None:
        await self._catalog.delete_like(user.id, track_id)
        await self._session.commit()

    async def start_play(
        self, user: User, track_id: uuid.UUID, source: str | None
    ) -> PlayStartResponse:
        track = await self._catalog.get_track(track_id)
        if track is None or track.status != TrackStatus.ready:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
        play = await self._catalog.create_play(user.id, track_id, source)
        track.play_count += 1
        await self._session.commit()
        return PlayStartResponse(play_id=play.id)

    async def heartbeat_play(
        self,
        user: User,
        play_id: int,
        payload: PlayHeartbeatRequest,
    ) -> None:
        play = await self._catalog.get_play(play_id, user.id)
        if play is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Play not found")
        play.listened_seconds = payload.listened_seconds
        play.completed = payload.completed
        await self._session.commit()

    async def list_genres(self) -> list[Genre]:
        return await self._catalog.list_genres()

    async def list_languages(self) -> list[Language]:
        return await self._catalog.list_languages()

    async def import_local_track(
        self,
        *,
        source_file: Path,
        title: str,
        artist_name: str,
        added_by_user_id: uuid.UUID,
        album_title: str | None = None,
    ) -> Track:
        from app.core.storage import copy_track_file

        artist = Artist(name=artist_name, sort_name=artist_name)
        await self._catalog.add(artist)
        album = None
        if album_title:
            album = Album(title=album_title, primary_artist_id=artist.id, is_single=True)
            await self._catalog.add(album)

        track = Track(
            title=title,
            album_id=album.id if album else None,
            file_path="pending",
            status=TrackStatus.ready,
            added_by_user_id=added_by_user_id,
            source_kind="upload",
        )
        await self._catalog.add(track)
        relative, extension, size, digest = copy_track_file(source_file, track.id)
        track.file_path = relative
        track.file_format = extension
        track.file_size_bytes = size
        track.audio_sha256 = digest
        track.updated_at = datetime.now(UTC)
        self._session.add(
            TrackArtist(track_id=track.id, artist_id=artist.id, role=ArtistRole.main, position=0)
        )
        await self._session.commit()
        await self._session.refresh(track)
        return track


class PlaylistService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._playlists = PlaylistRepository(session)
        self._catalog_repo = CatalogRepository(session)
        self._catalog = CatalogService(session)

    async def list_playlists(self, user: User) -> list[PlaylistSummary]:
        await self._catalog.ensure_favourite_playlist(user.id)
        playlists = await self._playlists.list_for_user(user.id)
        summaries: list[PlaylistSummary] = []
        for playlist in playlists:
            count = await self._playlists.count_tracks(playlist.id)
            summaries.append(
                PlaylistSummary(
                    id=playlist.id,
                    name=playlist.name,
                    is_favourite=playlist.is_favourite,
                    is_public=playlist.is_public,
                    track_count=count,
                    created_at=playlist.created_at,
                )
            )
        return summaries

    async def create_playlist(self, user: User, payload: PlaylistCreateRequest) -> PlaylistSummary:
        playlist = Playlist(
            owner_id=user.id,
            name=payload.name,
            is_public=payload.is_public,
            is_favourite=False,
        )
        await self._playlists.create(playlist)
        await self._session.commit()
        await self._session.refresh(playlist)
        return PlaylistSummary(
            id=playlist.id,
            name=playlist.name,
            is_favourite=playlist.is_favourite,
            is_public=playlist.is_public,
            track_count=0,
            created_at=playlist.created_at,
        )

    async def get_playlist(self, user: User, playlist_id: uuid.UUID) -> PlaylistDetail:
        playlist = await self._playlists.get_by_id(playlist_id)
        if playlist is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
        if playlist.owner_id != user.id and not playlist.is_public:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        track_items: list[PlaylistTrackItem] = []
        for link in sorted(playlist.tracks, key=lambda item: item.position):
            like = await self._catalog_repo.get_user_like(user.id, link.track_id)
            track_items.append(
                PlaylistTrackItem(
                    track=_track_list_item(link.track, like.sentiment if like else None),
                    position=link.position,
                    added_at=link.added_at,
                )
            )
        return PlaylistDetail(
            id=playlist.id,
            name=playlist.name,
            is_favourite=playlist.is_favourite,
            is_public=playlist.is_public,
            track_count=len(track_items),
            created_at=playlist.created_at,
            tracks=track_items,
        )

    async def update_playlist(
        self,
        user: User,
        playlist_id: uuid.UUID,
        payload: PlaylistUpdateRequest,
    ) -> PlaylistSummary:
        playlist = await self._get_owned_playlist(user, playlist_id)
        if payload.name is not None:
            playlist.name = payload.name
        if payload.is_public is not None:
            playlist.is_public = payload.is_public
        playlist.updated_at = datetime.now(UTC)
        await self._session.commit()
        count = await self._playlists.count_tracks(playlist.id)
        return PlaylistSummary(
            id=playlist.id,
            name=playlist.name,
            is_favourite=playlist.is_favourite,
            is_public=playlist.is_public,
            track_count=count,
            created_at=playlist.created_at,
        )

    async def delete_playlist(self, user: User, playlist_id: uuid.UUID) -> None:
        playlist = await self._get_owned_playlist(user, playlist_id)
        if playlist.is_favourite:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Favourite playlist cannot be deleted",
            )
        await self._playlists.delete(playlist)
        await self._session.commit()

    async def add_tracks(
        self,
        user: User,
        playlist_id: uuid.UUID,
        payload: PlaylistTracksRequest,
    ) -> PlaylistDetail:
        playlist = await self._get_owned_playlist(user, playlist_id)
        await self._playlists.add_tracks(playlist.id, payload.track_ids)
        await self._session.commit()
        return await self.get_playlist(user, playlist_id)

    async def remove_track(self, user: User, playlist_id: uuid.UUID, track_id: uuid.UUID) -> None:
        await self._get_owned_playlist(user, playlist_id)
        await self._playlists.remove_track(playlist_id, track_id)
        await self._session.commit()

    async def reorder(
        self,
        user: User,
        playlist_id: uuid.UUID,
        payload: PlaylistReorderRequest,
    ) -> PlaylistDetail:
        await self._get_owned_playlist(user, playlist_id)
        await self._playlists.reorder(playlist_id, payload.track_ids)
        await self._session.commit()
        return await self.get_playlist(user, playlist_id)

    async def _get_owned_playlist(self, user: User, playlist_id: uuid.UUID) -> Playlist:
        playlist = await self._playlists.get(playlist_id)
        if playlist is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
        if playlist.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return playlist
