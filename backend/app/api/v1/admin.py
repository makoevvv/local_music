import uuid

from fastapi import APIRouter

from app.core.deps import CurrentAdmin, CurrentMaster, DbSession
from app.schemas.auth import (
    CreateInviteRequest,
    CreateUserRequest,
    InviteResponse,
    UpdateUserRequest,
    UpdateUserRoleRequest,
    UserPublic,
)
from app.services.auth import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserPublic])
async def list_users(_admin: CurrentAdmin, session: DbSession) -> list[UserPublic]:
    return await AdminService(session).list_users()


@router.post("/users", response_model=UserPublic, status_code=201)
async def create_user(
    payload: CreateUserRequest,
    master: CurrentMaster,
    session: DbSession,
) -> UserPublic:
    return await AdminService(session).create_user(master, payload)


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: uuid.UUID,
    payload: UpdateUserRequest,
    admin: CurrentAdmin,
    session: DbSession,
) -> UserPublic:
    return await AdminService(session).update_user(admin, user_id, payload)


@router.patch("/users/{user_id}/role", response_model=UserPublic)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UpdateUserRoleRequest,
    master: CurrentMaster,
    session: DbSession,
) -> UserPublic:
    return await AdminService(session).update_user_role(master, user_id, payload)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    master: CurrentMaster,
    session: DbSession,
) -> None:
    await AdminService(session).delete_user(master, user_id)


@router.post("/invites", response_model=InviteResponse, status_code=201)
async def create_invite(
    payload: CreateInviteRequest,
    admin: CurrentAdmin,
    session: DbSession,
) -> InviteResponse:
    invite = await AdminService(session).create_invite(admin, payload)
    return InviteResponse.model_validate(invite)
