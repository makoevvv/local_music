from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.sync_redis import get_search_cache, set_search_cache
from app.models.search import SearchCandidate
from app.repositories.search import SearchRepository
from app.schemas.search import SearchCandidatePublic, SearchRequest, SearchResponse
from app.services.ytdlp import YtdlpSearchResult, search_entries


def normalize_query(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query.strip().lower())
    return normalized


def query_hash(query: str) -> str:
    return hashlib.sha256(normalize_query(query).encode()).hexdigest()


def _to_public(candidate: SearchCandidate) -> SearchCandidatePublic:
    payload = candidate.payload
    return SearchCandidatePublic(
        candidate_id=candidate.id,
        title=str(payload.get("title") or "Unknown"),
        artist=str(payload.get("artist") or "Unknown Artist"),
        duration_seconds=payload.get("duration_seconds"),
        thumbnail_url=payload.get("thumbnail_url"),
        source_kind=candidate.source_kind,
        source_id=candidate.source_id,
        tier=candidate.tier,
        restricted=candidate.tier >= 4,
    )


def _result_to_candidate(query_hash_value: str, result: YtdlpSearchResult) -> SearchCandidate:
    return SearchCandidate(
        query_hash=query_hash_value,
        source_kind=result.source_kind,
        source_id=result.source_id,
        tier=result.tier,
        payload={
            "title": result.title,
            "artist": result.artist,
            "duration_seconds": result.duration_seconds,
            "thumbnail_url": result.thumbnail_url,
            "source_url": result.source_url,
            "license": result.license,
            "raw": result.raw,
        },
    )


class SearchService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SearchRepository(session)

    async def search(self, payload: SearchRequest) -> SearchResponse:
        normalized = normalize_query(payload.query)
        hash_value = query_hash(normalized)
        ttl = timedelta(hours=settings.search_cache_ttl_hours)
        ttl_seconds = int(ttl.total_seconds())

        cached_ids = get_search_cache(hash_value)
        if cached_ids is not None:
            candidates: list[SearchCandidate] = []
            for candidate_id in cached_ids:
                candidate = await self._repo.get_by_id(uuid.UUID(candidate_id))
                if candidate is not None:
                    candidates.append(candidate)
            if candidates:
                return SearchResponse(
                    query=normalized,
                    cached=True,
                    items=[_to_public(item) for item in candidates],
                )

        db_cached = await self._repo.get_cached_candidates(hash_value, max_age=ttl)
        if db_cached:
            set_search_cache(hash_value, [str(item.id) for item in db_cached], ttl_seconds)
            return SearchResponse(
                query=normalized,
                cached=True,
                items=[_to_public(item) for item in db_cached],
            )

        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(
                    search_entries,
                    normalized,
                    limit=payload.limit,
                    include_soundcloud=True,
                ),
                timeout=settings.search_timeout_seconds,
            )
        except TimeoutError:
            return SearchResponse(
                query=normalized,
                cached=False,
                items=[],
                warning=(
                    "Search timed out. The backend container may have no access to "
                    "YouTube/SoundCloud. Run: docker compose exec backend "
                    "curl -I --max-time 10 https://www.youtube.com"
                ),
            )

        warning = None
        if not results:
            warning = (
                "No results from YouTube/SoundCloud. "
                "Check that the backend container can reach the internet (e.g. curl https://www.youtube.com)."
            )
        candidates = [_result_to_candidate(hash_value, item) for item in results]
        if candidates:
            await self._repo.replace_candidates(hash_value, candidates)
            await self._session.commit()
            set_search_cache(hash_value, [str(item.id) for item in candidates], ttl_seconds)
        return SearchResponse(
            query=normalized,
            cached=False,
            items=[_to_public(item) for item in candidates],
            warning=warning,
        )
