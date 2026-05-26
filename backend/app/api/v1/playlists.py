import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.catalog import (
    PlaylistCreateRequest,
    PlaylistDetail,
    PlaylistReorderRequest,
    PlaylistSummary,
    PlaylistTracksRequest,
    PlaylistUpdateRequest,
)
from app.services.catalog import PlaylistService

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.get("", response_model=list[PlaylistSummary])
async def list_playlists(user: CurrentUser, session: DbSession) -> list[PlaylistSummary]:
    return await PlaylistService(session).list_playlists(user)


@router.post("", response_model=PlaylistSummary, status_code=201)
async def create_playlist(
    payload: PlaylistCreateRequest,
    user: CurrentUser,
    session: DbSession,
) -> PlaylistSummary:
    return await PlaylistService(session).create_playlist(user, payload)


@router.get("/{playlist_id}", response_model=PlaylistDetail)
async def get_playlist(
    playlist_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
) -> PlaylistDetail:
    return await PlaylistService(session).get_playlist(user, playlist_id)


@router.patch("/{playlist_id}", response_model=PlaylistSummary)
async def update_playlist(
    playlist_id: uuid.UUID,
    payload: PlaylistUpdateRequest,
    user: CurrentUser,
    session: DbSession,
) -> PlaylistSummary:
    return await PlaylistService(session).update_playlist(user, playlist_id, payload)


@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(
    playlist_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    await PlaylistService(session).delete_playlist(user, playlist_id)


@router.post("/{playlist_id}/tracks", response_model=PlaylistDetail)
async def add_tracks(
    playlist_id: uuid.UUID,
    payload: PlaylistTracksRequest,
    user: CurrentUser,
    session: DbSession,
) -> PlaylistDetail:
    return await PlaylistService(session).add_tracks(user, playlist_id, payload)


@router.delete("/{playlist_id}/tracks/{track_id}", status_code=204)
async def remove_track(
    playlist_id: uuid.UUID,
    track_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
) -> None:
    await PlaylistService(session).remove_track(user, playlist_id, track_id)


@router.post("/{playlist_id}/reorder", response_model=PlaylistDetail)
async def reorder_playlist(
    playlist_id: uuid.UUID,
    payload: PlaylistReorderRequest,
    user: CurrentUser,
    session: DbSession,
) -> PlaylistDetail:
    return await PlaylistService(session).reorder(user, playlist_id, payload)
