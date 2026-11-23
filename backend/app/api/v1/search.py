from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search import SearchService

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_tracks(
    payload: SearchRequest,
    _user: CurrentUser,
    session: DbSession,
) -> SearchResponse:
    return await SearchService(session).search(payload)
