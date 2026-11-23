from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rq_queue import get_queue
from app.models.catalog import Artist, ArtistRole, Track, TrackArtist, TrackStatus
from app.repositories.search import SearchRepository
from app.schemas.search import FromCandidateRequest, FromCandidateResponse, TrackStatusResponse
from app.workers.tasks import download_track_job


class SourcingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._search = SearchRepository(session)

    async def create_track_from_candidate(
        self,
        user_id: uuid.UUID,
        payload: FromCandidateRequest,
    ) -> FromCandidateResponse:
        candidate = await self._search.get_by_id(payload.candidate_id)
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

        data = candidate.payload
        artist_name = str(data.get("artist") or "Unknown Artist")
        title = str(data.get("title") or "Unknown Track")

        artist = Artist(name=artist_name, sort_name=artist_name)
        self._session.add(artist)
        await self._session.flush()

        track = Track(
            title=title,
            file_path="pending",
            status=TrackStatus.downloading,
            source_kind=candidate.source_kind,
            source_id=candidate.source_id,
            source_url=str(data.get("source_url") or ""),
            cover_url_origin=data.get("thumbnail_url"),
            duration_seconds=data.get("duration_seconds"),
            added_by_user_id=user_id,
            metadata_={"candidate_id": str(candidate.id)},
        )
        self._session.add(track)
        await self._session.flush()
        self._session.add(
            TrackArtist(
                track_id=track.id,
                artist_id=artist.id,
                role=ArtistRole.main,
                position=0,
            )
        )
        await self._session.commit()

        queue = get_queue()
        queue.enqueue(
            download_track_job,
            str(track.id),
            str(candidate.id),
            str(user_id),
            job_timeout=600,
        )

        return FromCandidateResponse(track_id=track.id, status=track.status.value)

    async def get_track_status(
        self, user_id: uuid.UUID, track_id: uuid.UUID
    ) -> TrackStatusResponse:
        track = await self._session.get(Track, track_id)
        if track is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Track not found")

        error = None
        existing_track_id = None
        if track.metadata_:
            error = track.metadata_.get("error")
            existing_raw = track.metadata_.get("existing_track_id")
            if existing_raw:
                existing_track_id = uuid.UUID(str(existing_raw))

        return TrackStatusResponse(
            track_id=track.id,
            status=track.status.value,
            error=str(error) if error else None,
            existing_track_id=existing_track_id,
        )
