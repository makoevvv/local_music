import uuid

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.core.deps import CurrentUser, DbSession
from app.schemas.catalog import (
    LikeRequest,
    PlayHeartbeatRequest,
    PlayStartResponse,
    TrackDetail,
    TrackListResponse,
)
from app.schemas.search import FromCandidateRequest, FromCandidateResponse, TrackStatusResponse
from app.services.catalog import CatalogService
from app.services.sourcing import SourcingService

router = APIRouter(tags=["tracks"])


@router.get("/tracks", response_model=TrackListResponse)
async def list_tracks(
    user: CurrentUser,
    session: DbSession,
    q: str | None = None,
    genre: str | None = None,
    language: str | None = None,
    has_lyrics: bool | None = None,
    sort: str = Query(default="recent", pattern="^(recent|title|plays)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> TrackListResponse:
    return await CatalogService(session).list_tracks(
        user,
        q=q,
        genre=genre,
        language=language,
        has_lyrics=has_lyrics,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.post("/tracks/from-candidate", response_model=FromCandidateResponse, status_code=201)
async def create_track_from_candidate(
    payload: FromCandidateRequest,
    user: CurrentUser,
    session: DbSession,
) -> FromCandidateResponse:
    return await SourcingService(session).create_track_from_candidate(user.id, payload)


@router.get("/tracks/{track_id}/status", response_model=TrackStatusResponse)
async def get_track_status(
    track_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
) -> TrackStatusResponse:
    return await SourcingService(session).get_track_status(user.id, track_id)


@router.get("/tracks/{track_id}", response_model=TrackDetail)
async def get_track(track_id: uuid.UUID, user: CurrentUser, session: DbSession) -> TrackDetail:
    return await CatalogService(session).get_track(user, track_id)


@router.get("/tracks/{track_id}/stream")
async def stream_track(
    track_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
) -> FileResponse:
    return await CatalogService(session).stream_track(user, track_id)


@router.post("/tracks/{track_id}/play", response_model=PlayStartResponse, status_code=201)
async def start_play(
    track_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    source: str | None = None,
) -> PlayStartResponse:
    return await CatalogService(session).start_play(user, track_id, source)


@router.post("/plays/{play_id}/heartbeat", status_code=204)
async def play_heartbeat(
    play_id: int,
    payload: PlayHeartbeatRequest,
    user: CurrentUser,
    session: DbSession,
) -> None:
    await CatalogService(session).heartbeat_play(user, play_id, payload)


@router.put("/tracks/{track_id}/like", status_code=204)
async def like_track(
    track_id: uuid.UUID,
    payload: LikeRequest,
    user: CurrentUser,
    session: DbSession,
) -> None:
    await CatalogService(session).set_like(user, track_id, payload)


@router.delete("/tracks/{track_id}/like", status_code=204)
async def unlike_track(track_id: uuid.UUID, user: CurrentUser, session: DbSession) -> None:
    await CatalogService(session).remove_like(user, track_id)
