from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, DbSession
from app.schemas.catalog import TrackListItem
from app.services.vibe.service import VibeService

router = APIRouter(prefix="/vibe", tags=["vibe"])


class VibeSessionRequest(BaseModel):
    mood: str = "neutral"
    genres: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    mode: str = "mixed"
    explicit_allowed: bool = True
    no_lyrics: bool = False


class VibeQueueResponse(BaseModel):
    session_id: uuid.UUID
    queue: list[TrackListItem]


class VibeFeedbackRequest(BaseModel):
    track_id: uuid.UUID
    action: str


class VibePresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    mood: str = "neutral"
    genres: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    mode: str = "mixed"
    explicit_allowed: bool = True
    no_lyrics: bool = False


class VibePresetPublic(BaseModel):
    id: uuid.UUID
    name: str
    settings: dict[str, object]


@router.post("/session", response_model=VibeQueueResponse, status_code=201)
async def start_session(
    payload: VibeSessionRequest, user: CurrentUser, session: DbSession
) -> VibeQueueResponse:
    session_id, queue = await VibeService(session).start(
        user.id,
        mood=payload.mood,
        genres=payload.genres,
        languages=payload.languages,
        mode=payload.mode,
        explicit_allowed=payload.explicit_allowed,
        no_lyrics=payload.no_lyrics,
    )
    return VibeQueueResponse(session_id=uuid.UUID(session_id), queue=queue)


@router.post("/{session_id}/next", response_model=VibeQueueResponse)
async def next_batch(
    session_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> VibeQueueResponse:
    queue = await VibeService(session).next_batch(user.id, str(session_id))
    return VibeQueueResponse(session_id=session_id, queue=queue)


@router.post("/{session_id}/feedback", status_code=204, response_class=Response)
async def feedback(
    session_id: uuid.UUID,
    payload: VibeFeedbackRequest,
    user: CurrentUser,
    session: DbSession,
) -> Response:
    await VibeService(session).feedback(
        user.id,
        str(session_id),
        track_id=payload.track_id,
        action=payload.action,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/presets", response_model=list[VibePresetPublic])
async def list_presets(user: CurrentUser, session: DbSession) -> list[VibePresetPublic]:
    rows = await VibeService(session).list_presets(user.id)
    return [
        VibePresetPublic(id=row.id, name=row.name, settings=dict(row.settings)) for row in rows
    ]


@router.post("/presets", response_model=VibePresetPublic, status_code=201)
async def save_preset(
    payload: VibePresetRequest, user: CurrentUser, session: DbSession
) -> VibePresetPublic:
    row = await VibeService(session).save_preset(
        user.id,
        name=payload.name,
        settings=payload.model_dump(exclude={"name"}),
    )
    return VibePresetPublic(id=row.id, name=row.name, settings=dict(row.settings))
