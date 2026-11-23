from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.models.imports import ExternalAccount, ImportItem, ImportJob
from app.services.imports.jobs import (
    create_file_job,
    finish_spotify_callback,
    resolve_item_choice,
    save_account,
    spotify_connect_url,
    start_provider_job,
)
from app.services.imports.providers import spotify_configured

router = APIRouter(prefix="/import", tags=["import"])


class ProviderStatus(BaseModel):
    provider: str
    configured: bool
    connected: bool


class ImportJobPublic(BaseModel):
    id: uuid.UUID
    provider: str
    status: str
    total_tracks: int
    resolved_tracks: int
    ambiguous_tracks: int
    failed_tracks: int
    result_summary: dict[str, object] = Field(default_factory=dict)


class ImportItemPublic(BaseModel):
    id: uuid.UUID
    position: int
    title: str
    artist: str
    album: str | None
    playlist_name: str
    status: str
    matched_track_id: uuid.UUID | None
    candidates: list[dict[str, object]]


class YandexTokenRequest(BaseModel):
    token: str = Field(min_length=8)


class ResolveItemRequest(BaseModel):
    track_id: uuid.UUID | None = None
    source_key: str | None = None


class StartImportRequest(BaseModel):
    mode: str = "add"
    auto_threshold: float = 0.85
    create_missing: bool = True


def _job_public(job: ImportJob) -> ImportJobPublic:
    return ImportJobPublic(
        id=job.id,
        provider=job.provider,
        status=job.status,
        total_tracks=job.total_tracks,
        resolved_tracks=job.resolved_tracks,
        ambiguous_tracks=job.ambiguous_tracks,
        failed_tracks=job.failed_tracks,
        result_summary=job.result_summary or {},
    )


@router.get("/providers", response_model=list[ProviderStatus])
async def list_providers(user: CurrentUser, session: DbSession) -> list[ProviderStatus]:
    connected = {
        row.provider
        for row in (
            await session.scalars(select(ExternalAccount).where(ExternalAccount.user_id == user.id))
        ).all()
    }
    return [
        ProviderStatus(provider="file", configured=True, connected=True),
        ProviderStatus(
            provider="spotify", configured=spotify_configured(), connected="spotify" in connected
        ),
        ProviderStatus(provider="yandex", configured=True, connected="yandex" in connected),
        ProviderStatus(provider="apple", configured=False, connected=False),
    ]


@router.get("/spotify/connect")
async def connect_spotify(user: CurrentUser) -> dict[str, str]:
    try:
        return {"authorize_url": spotify_connect_url(user.id)}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


@router.get("/callback/spotify")
async def spotify_callback(
    session: DbSession,
    code: str = "",
    state: str = "",
) -> RedirectResponse:
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OAuth code")
    try:
        await finish_spotify_callback(session, code=code, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(settings.spotify_redirect_web or "http://localhost:3000/import")


@router.post("/connect/yandex", status_code=204, response_class=Response)
async def connect_yandex(
    payload: YandexTokenRequest, user: CurrentUser, session: DbSession
) -> Response:
    await save_account(
        session,
        user_id=user.id,
        provider="yandex",
        access_token=payload.token,
        refresh_token=None,
        external_user_id=None,
    )
    return Response(status_code=204)


@router.delete("/accounts/{provider}", status_code=204, response_class=Response)
async def disconnect_account(provider: str, user: CurrentUser, session: DbSession) -> Response:
    account = await session.scalar(
        select(ExternalAccount).where(
            ExternalAccount.user_id == user.id,
            ExternalAccount.provider == provider,
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not connected")
    await session.delete(account)
    await session.commit()
    return Response(status_code=204)


@router.post("/file", response_model=ImportJobPublic, status_code=201)
async def import_file(
    user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
    mode: Annotated[str, Form()] = "add",
    auto_threshold: Annotated[float, Form()] = 0.85,
    create_missing: Annotated[bool, Form()] = True,
) -> ImportJobPublic:
    raw = await file.read()
    if len(raw) > 5_000_000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5 MB"
        )
    try:
        job = await create_file_job(
            session,
            user_id=user.id,
            filename=file.filename or "import.csv",
            raw=raw,
            mode=mode if mode in {"add", "replace"} else "add",
            auto_threshold=auto_threshold,
            create_missing=create_missing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _job_public(job)


@router.post("/{provider}/start", response_model=ImportJobPublic, status_code=201)
async def start_provider_import(
    provider: str,
    payload: StartImportRequest,
    user: CurrentUser,
    session: DbSession,
) -> ImportJobPublic:
    if provider not in {"spotify", "yandex"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown provider")
    try:
        job = await start_provider_job(
            session,
            user_id=user.id,
            provider=provider,
            mode=payload.mode if payload.mode in {"add", "replace"} else "add",
            auto_threshold=payload.auto_threshold,
            create_missing=payload.create_missing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _job_public(job)


@router.get("/jobs", response_model=list[ImportJobPublic])
async def list_jobs(user: CurrentUser, session: DbSession) -> list[ImportJobPublic]:
    rows = (
        await session.scalars(
            select(ImportJob)
            .where(ImportJob.user_id == user.id)
            .order_by(ImportJob.created_at.desc())
        )
    ).all()
    return [_job_public(job) for job in rows]


@router.get("/jobs/{job_id}", response_model=ImportJobPublic)
async def get_job(job_id: uuid.UUID, user: CurrentUser, session: DbSession) -> ImportJobPublic:
    job = await session.get(ImportJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return _job_public(job)


@router.get("/jobs/{job_id}/items", response_model=list[ImportItemPublic])
async def list_items(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    item_status: str | None = Query(default=None, alias="status"),
) -> list[ImportItemPublic]:
    job = await session.get(ImportJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    stmt = select(ImportItem).where(ImportItem.job_id == job.id).order_by(ImportItem.position)
    if item_status:
        stmt = stmt.where(ImportItem.status == item_status)
    rows = (await session.scalars(stmt)).all()
    return [
        ImportItemPublic(
            id=item.id,
            position=item.position,
            title=item.title,
            artist=item.artist,
            album=item.album,
            playlist_name=item.playlist_name,
            status=item.status,
            matched_track_id=item.matched_track_id,
            candidates=item.candidates or [],
        )
        for item in rows
    ]


@router.post("/jobs/{job_id}/items/{item_id}/resolve", response_model=ImportItemPublic)
async def resolve_item(
    job_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ResolveItemRequest,
    user: CurrentUser,
    session: DbSession,
) -> ImportItemPublic:
    try:
        item = await resolve_item_choice(
            session,
            user_id=user.id,
            job_id=job_id,
            item_id=item_id,
            track_id=payload.track_id,
            source_key=payload.source_key,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ImportItemPublic(
        id=item.id,
        position=item.position,
        title=item.title,
        artist=item.artist,
        album=item.album,
        playlist_name=item.playlist_name,
        status=item.status,
        matched_track_id=item.matched_track_id,
        candidates=item.candidates or [],
    )


@router.post("/jobs/{job_id}/cancel", status_code=204, response_class=Response)
async def cancel_job(job_id: uuid.UUID, user: CurrentUser, session: DbSession) -> Response:
    job = await session.get(ImportJob, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    job.status = "cancelled"
    await session.commit()
    return Response(status_code=204)
