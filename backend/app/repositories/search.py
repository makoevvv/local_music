from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search import SearchCandidate


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_cached_candidates(
        self, query_hash: str, *, max_age: timedelta
    ) -> list[SearchCandidate]:
        cutoff = datetime.now(UTC) - max_age
        result = await self._session.execute(
            select(SearchCandidate)
            .where(SearchCandidate.query_hash == query_hash, SearchCandidate.created_at >= cutoff)
            .order_by(SearchCandidate.tier.asc(), SearchCandidate.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, candidate_id: uuid.UUID) -> SearchCandidate | None:
        return await self._session.get(SearchCandidate, candidate_id)

    async def replace_candidates(
        self,
        query_hash: str,
        candidates: list[SearchCandidate],
    ) -> list[SearchCandidate]:
        await self._session.execute(
            delete(SearchCandidate).where(SearchCandidate.query_hash == query_hash)
        )
        for candidate in candidates:
            self._session.add(candidate)
        await self._session.flush()
        return candidates
