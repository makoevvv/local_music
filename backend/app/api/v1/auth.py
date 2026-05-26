from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserPublic,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=201)
async def register(payload: RegisterRequest, session: DbSession) -> UserPublic:
    return await AuthService(session).register(payload)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: DbSession) -> TokenResponse:
    return await AuthService(session).login(payload)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, session: DbSession) -> TokenResponse:
    return await AuthService(session).refresh(payload.refresh_token)


@router.post("/logout", status_code=204)
async def logout(payload: LogoutRequest, session: DbSession) -> None:
    await AuthService(session).logout(payload.refresh_token)


@router.get("/me", response_model=UserPublic)
async def me(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_me(
    payload: UpdateMeRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> UserPublic:
    return await AuthService(session).update_me(current_user, payload)
