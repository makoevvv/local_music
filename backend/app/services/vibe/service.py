from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import (
    Genre,
    Language,
    Play,
    Track,
    TrackArtist,
    TrackGenre,
    TrackLanguage,
    TrackStatus,
)
from app.models.vibe import VibePreset
from app.schemas.catalog import TrackListItem
from app.services.catalog import _track_list_item
from app.services.vibe.feedback import (
    AFFINITY_WEIGHTS,
    apply_feedback,
    read_affinity,
    read_affinity_map,
)
from app.services.vibe.mood_profiles import MOODS, mood_profile
from app.services.vibe.pool import Candidate, select_candidates
from app.services.vibe.scorer import (
    boltzmann_sample,
    mood_match,
    novelty_for,
    popularity,
    score_parts,
    squash_affinity,
)
from app.services.vibe.session import VibeState, load_session, save_session

BATCH_SIZE = 5
COLD_START_PLAYS = 20
MODES = {"familiar", "discover", "mixed"}


class VibeService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(
        self,
        user_id: uuid.UUID,
        *,
        mood: str,
        genres: list[str],
        languages: list[str],
        mode: str,
        explicit_allowed: bool,
        no_lyrics: bool,
    ) -> tuple[str, list[TrackListItem]]:
        if mood not in MOODS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown mood")
        if mode not in MODES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown mode")
        session_id = str(uuid.uuid4())
        state = VibeState(
            user_id=str(user_id),
            mood=mood,
            genres=genres,
            languages=languages,
            mode=mode,
            explicit_allowed=explicit_allowed,
            no_lyrics=no_lyrics,
            seed=int(uuid.uuid4().int % 1_000_000),
            batch=0,
            excluded=[],
        )
        queue = await self._next_from_state(user_id, state)
        save_session(session_id, state)
        return session_id, queue

    async def next_batch(self, user_id: uuid.UUID, session_id: str) -> list[TrackListItem]:
        state = self._owned(user_id, session_id)
        queue = await self._next_from_state(user_id, state)
        save_session(session_id, state)
        return queue

    async def feedback(
        self,
        user_id: uuid.UUID,
        session_id: str,
        *,
        track_id: uuid.UUID,
        action: str,
    ) -> None:
        state = self._owned(user_id, session_id)
        if action not in AFFINITY_WEIGHTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown action")
        track = await self._session.get(
            Track,
            track_id,
            options=(selectinload(Track.artists),),
        )
        if track is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")
        artist_ids = [str(link.artist_id) for link in track.artists]
        genre_ids = [
            str(row)
            for row in (
                await self._session.scalars(
                    select(TrackGenre.genre_id).where(TrackGenre.track_id == track.id)
                )
            ).all()
        ]
        await apply_feedback(
            self._session,
            user_id=user_id,
            artist_ids=artist_ids,
            genre_ids=genre_ids,
            action=action,
        )
        if action == "dislike":
            excluded = list(state["excluded"])
            if str(track_id) not in excluded:
                excluded.append(str(track_id))
            state["excluded"] = excluded
        save_session(session_id, state)

    async def list_presets(self, user_id: uuid.UUID) -> list[VibePreset]:
        return list(
            (
                await self._session.scalars(
                    select(VibePreset)
                    .where(VibePreset.user_id == user_id)
                    .order_by(VibePreset.created_at.desc())
                )
            ).all()
        )

    async def save_preset(
        self,
        user_id: uuid.UUID,
        *,
        name: str,
        settings: dict[str, object],
    ) -> VibePreset:
        existing = await self._session.scalar(
            select(VibePreset).where(VibePreset.user_id == user_id, VibePreset.name == name)
        )
        if existing is None:
            existing = VibePreset(user_id=user_id, name=name, settings=dict(settings))
            self._session.add(existing)
        else:
            existing.settings = dict(settings)
        await self._session.commit()
        await self._session.refresh(existing)
        return existing

    def _owned(self, user_id: uuid.UUID, session_id: str) -> VibeState:
        state = load_session(session_id)
        if state is None or state["user_id"] != str(user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vibe session not found")
        return state

    async def _next_from_state(self, user_id: uuid.UUID, state: VibeState) -> list[TrackListItem]:
        profile = mood_profile(state["mood"])
        library = await self._library(user_id)
        chosen_pool = select_candidates(
            library,
            profile=profile,
            genres=state["genres"],
            languages=state["languages"],
            explicit_allowed=state["explicit_allowed"],
            no_lyrics=state["no_lyrics"],
            excluded=set(state["excluded"]),
        )
        total_plays = sum(item.user_plays for item in library)
        temperature = 1.4 if total_plays < COLD_START_PLAYS else 0.6
        preferred = {
            genre_id
            for genre_id, score in read_affinity_map(user_id, "genre").items()
            if score > 0 and not profile.genres
        }
        scored: list[tuple[str, float]] = []
        for candidate in chosen_pool:
            raw_scores = _raw_affinity(user_id, candidate)
            affinity = squash_affinity(sum(raw_scores) / len(raw_scores)) if raw_scores else 0.0
            dislike = 1.0 if any(value <= -5 for value in raw_scores) else 0.0
            scored.append(
                (
                    candidate.track_id,
                    score_parts(
                        mood_match=mood_match(
                            bpm=candidate.bpm,
                            energy=candidate.energy,
                            valence=candidate.valence,
                            genre_names=candidate.genre_names,
                            genre_ids=candidate.genre_ids,
                            profile=profile,
                            preferred_genre_ids=preferred,
                        ),
                        affinity=affinity,
                        novelty=novelty_for(state["mode"], candidate.user_plays),
                        popularity=popularity(candidate.play_count),
                        recent=1.0 if candidate.recently_played else 0.0,
                        dislike=dislike,
                    ),
                )
            )
        seed = state["seed"] + state["batch"]
        chosen = boltzmann_sample(scored, BATCH_SIZE, seed, temperature)
        state["batch"] = state["batch"] + 1
        return await self._public(chosen)

    async def _public(self, track_ids: list[str]) -> list[TrackListItem]:
        items: list[TrackListItem] = []
        for raw_id in track_ids:
            track = await self._session.get(
                Track,
                uuid.UUID(raw_id),
                options=(
                    selectinload(Track.artists).selectinload(TrackArtist.artist),
                    selectinload(Track.album),
                ),
            )
            if track is not None:
                items.append(_track_list_item(track))
        return items

    async def _library(self, user_id: uuid.UUID) -> list[Candidate]:
        tracks = (
            await self._session.scalars(
                select(Track)
                .where(Track.status == TrackStatus.ready)
                .options(selectinload(Track.artists))
            )
        ).all()
        genre_names: dict[uuid.UUID, list[str]] = {}
        genre_ids: dict[uuid.UUID, list[str]] = {}
        genre_rows = (
            await self._session.execute(
                select(TrackGenre.track_id, TrackGenre.genre_id, Genre.slug, Genre.name).join(
                    Genre, Genre.id == TrackGenre.genre_id
                )
            )
        ).all()
        for track_id, genre_id, slug, name in genre_rows:
            genre_names.setdefault(track_id, []).extend([str(slug).lower(), str(name).lower()])
            genre_ids.setdefault(track_id, []).append(str(genre_id))
        language_codes: dict[uuid.UUID, list[str]] = {}
        language_rows = (
            await self._session.execute(
                select(TrackLanguage.track_id, Language.code).join(
                    Language, Language.id == TrackLanguage.language_id
                )
            )
        ).all()
        for track_id, code in language_rows:
            language_codes.setdefault(track_id, []).append(str(code))
        play_rows = (
            await self._session.execute(
                select(Play.track_id, func.count())
                .where(Play.user_id == user_id)
                .group_by(Play.track_id)
            )
        ).all()
        plays = {track_id: int(count) for track_id, count in play_rows}
        since = datetime.now(UTC) - timedelta(hours=6)
        recent = set(
            (
                await self._session.scalars(
                    select(Play.track_id).where(Play.user_id == user_id, Play.started_at >= since)
                )
            ).all()
        )
        return [
            Candidate(
                track_id=str(track.id),
                bpm=track.bpm,
                energy=track.energy,
                valence=track.valence,
                genre_names=tuple(genre_names.get(track.id, [])),
                genre_ids=tuple(genre_ids.get(track.id, [])),
                artist_ids=tuple(str(link.artist_id) for link in track.artists),
                language_codes=tuple(language_codes.get(track.id, [])),
                explicit=track.explicit,
                has_lyrics=track.has_lyrics,
                play_count=track.play_count,
                user_plays=plays.get(track.id, 0),
                recently_played=track.id in recent,
            )
            for track in tracks
        ]


def _raw_affinity(user_id: uuid.UUID, candidate: Candidate) -> list[float]:
    values: list[float] = []
    for artist_id in candidate.artist_ids:
        stored = read_affinity(user_id, "artist", artist_id)
        if stored is not None:
            values.append(stored)
    for genre_id in candidate.genre_ids:
        stored = read_affinity(user_id, "genre", genre_id)
        if stored is not None:
            values.append(stored)
    return values
