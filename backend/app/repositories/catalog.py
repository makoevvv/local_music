from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import (
    Album,
    Artist,
    Genre,
    Language,
    Like,
    LikeSentiment,
    Play,
    Playlist,
    PlaylistTrack,
    Track,
    TrackArtist,
    TrackGenre,
    TrackLanguage,
    TrackStatus,
)


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _track_query(self) -> Select[tuple[Track]]:
        return select(Track).options(
            selectinload(Track.artists).selectinload(TrackArtist.artist),
            selectinload(Track.album),
        )

    async def list_tracks(
        self,
        *,
        q: str | None,
        genre_slug: str | None,
        language_code: str | None,
        has_lyrics: bool | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Track], int]:
        stmt = self._track_query().where(Track.status == TrackStatus.ready)

        if q:
            stmt = stmt.where(Track.title.ilike(f"%{q}%"))
        if has_lyrics is not None:
            stmt = stmt.where(Track.has_lyrics.is_(has_lyrics))
        if genre_slug:
            stmt = stmt.join(TrackGenre, TrackGenre.track_id == Track.id).join(Genre).where(
                Genre.slug == genre_slug
            )
        if language_code:
            stmt = stmt.join(TrackLanguage, TrackLanguage.track_id == Track.id).join(Language).where(
                Language.code == language_code
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one())

        if sort == "title":
            stmt = stmt.order_by(Track.title.asc())
        elif sort == "plays":
            stmt = stmt.order_by(Track.play_count.desc(), Track.title.asc())
        else:
            stmt = stmt.order_by(Track.created_at.desc())

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_track(self, track_id: uuid.UUID) -> Track | None:
        stmt = (
            self._track_query()
            .where(Track.id == track_id)
            .options(
                selectinload(Track.artists).selectinload(TrackArtist.artist),
            )
        )
        result = await self._session.execute(stmt)
        track = result.scalar_one_or_none()
        if track is None:
            return None
        await self._session.refresh(track, attribute_names=["album"])
        return track

    async def get_track_with_relations(self, track_id: uuid.UUID) -> Track | None:
        track = await self.get_track(track_id)
        return track

    async def get_user_like(self, user_id: uuid.UUID, track_id: uuid.UUID) -> Like | None:
        result = await self._session.execute(
            select(Like).where(Like.user_id == user_id, Like.track_id == track_id)
        )
        return result.scalar_one_or_none()

    async def set_like(
        self,
        user_id: uuid.UUID,
        track_id: uuid.UUID,
        sentiment: LikeSentiment,
    ) -> Like:
        existing = await self.get_user_like(user_id, track_id)
        if existing is not None:
            existing.sentiment = sentiment
            await self._session.flush()
            return existing
        like = Like(user_id=user_id, track_id=track_id, sentiment=sentiment)
        self._session.add(like)
        await self._session.flush()
        return like

    async def delete_like(self, user_id: uuid.UUID, track_id: uuid.UUID) -> None:
        existing = await self.get_user_like(user_id, track_id)
        if existing is not None:
            await self._session.delete(existing)
            await self._session.flush()

    async def list_genres(self) -> list[Genre]:
        result = await self._session.execute(select(Genre).order_by(Genre.name))
        return list(result.scalars().all())

    async def list_languages(self) -> list[Language]:
        result = await self._session.execute(select(Language).order_by(Language.name))
        return list(result.scalars().all())

    async def get_genres_for_track(self, track_id: uuid.UUID) -> list[Genre]:
        result = await self._session.execute(
            select(Genre)
            .join(TrackGenre, TrackGenre.genre_id == Genre.id)
            .where(TrackGenre.track_id == track_id)
            .order_by(Genre.name)
        )
        return list(result.scalars().all())

    async def get_languages_for_track(self, track_id: uuid.UUID) -> list[Language]:
        result = await self._session.execute(
            select(Language)
            .join(TrackLanguage, TrackLanguage.language_id == Language.id)
            .where(TrackLanguage.track_id == track_id)
            .order_by(Language.name)
        )
        return list(result.scalars().all())

    async def create_play(self, user_id: uuid.UUID, track_id: uuid.UUID, source: str | None) -> Play:
        play = Play(user_id=user_id, track_id=track_id, source=source)
        self._session.add(play)
        await self._session.flush()
        return play

    async def get_play(self, play_id: int, user_id: uuid.UUID) -> Play | None:
        result = await self._session.execute(
            select(Play).where(Play.id == play_id, Play.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def add(self, entity: Artist | Track | Album) -> None:
        self._session.add(entity)
        await self._session.flush()


class PlaylistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_favourite(self, owner_id: uuid.UUID) -> Playlist | None:
        result = await self._session.execute(
            select(Playlist).where(Playlist.owner_id == owner_id, Playlist.is_favourite.is_(True))
        )
        return result.scalar_one_or_none()

    async def create(self, playlist: Playlist) -> Playlist:
        self._session.add(playlist)
        await self._session.flush()
        return playlist

    async def list_for_user(self, user_id: uuid.UUID) -> list[Playlist]:
        result = await self._session.execute(
            select(Playlist)
            .where(or_(Playlist.owner_id == user_id, Playlist.is_public.is_(True)))
            .order_by(Playlist.is_favourite.desc(), Playlist.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, playlist_id: uuid.UUID) -> Playlist | None:
        result = await self._session.execute(
            select(Playlist)
            .where(Playlist.id == playlist_id)
            .options(
                selectinload(Playlist.tracks)
                .selectinload(PlaylistTrack.track)
                .selectinload(Track.artists)
                .selectinload(TrackArtist.artist),
                selectinload(Playlist.tracks).selectinload(PlaylistTrack.track).selectinload(Track.album),
            )
        )
        return result.scalar_one_or_none()

    async def count_tracks(self, playlist_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id)
        )
        return int(result.scalar_one())

    async def add_tracks(self, playlist_id: uuid.UUID, track_ids: list[uuid.UUID]) -> None:
        result = await self._session.execute(
            select(func.coalesce(func.max(PlaylistTrack.position), -1))
            .select_from(PlaylistTrack)
            .where(PlaylistTrack.playlist_id == playlist_id)
        )
        position = int(result.scalar_one()) + 1
        for track_id in track_ids:
            existing = await self._session.execute(
                select(PlaylistTrack).where(
                    PlaylistTrack.playlist_id == playlist_id,
                    PlaylistTrack.track_id == track_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            self._session.add(
                PlaylistTrack(playlist_id=playlist_id, track_id=track_id, position=position)
            )
            position += 1
        await self._session.flush()

    async def remove_track(self, playlist_id: uuid.UUID, track_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(PlaylistTrack).where(
                PlaylistTrack.playlist_id == playlist_id,
                PlaylistTrack.track_id == track_id,
            )
        )
        item = result.scalar_one_or_none()
        if item is not None:
            await self._session.delete(item)
            await self._session.flush()

    async def reorder(self, playlist_id: uuid.UUID, track_ids: list[uuid.UUID]) -> None:
        result = await self._session.execute(
            select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id)
        )
        items = {item.track_id: item for item in result.scalars().all()}
        for index, track_id in enumerate(track_ids):
            if track_id in items:
                items[track_id].position = index
        await self._session.flush()

    async def delete(self, playlist: Playlist) -> None:
        await self._session.delete(playlist)
        await self._session.flush()
