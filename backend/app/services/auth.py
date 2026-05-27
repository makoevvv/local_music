from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_ttl,
    verify_password,
)
from app.models.invite import Invite
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.repositories.user import (
    AuditLogRepository,
    InviteRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.schemas.auth import (
    CreateInviteRequest,
    CreateUserRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UpdateUserRequest,
    UpdateUserRoleRequest,
    UserPublic,
)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._invites = InviteRepository(session)
        self._refresh = RefreshTokenRepository(session)
        self._audit = AuditLogRepository(session)

    async def register(self, payload: RegisterRequest) -> UserPublic:
        if not settings.registration_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Registration disabled"
            )
        if settings.registration_invite_only:
            invite = await self._invites.get_by_code(payload.invite_code)
            if invite is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite code"
                )
            if invite.used_by_user_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invite already used"
                )
            if invite.expires_at and invite.expires_at < datetime.now(UTC):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invite expired"
                )
        else:
            invite = None

        if await self._users.get_by_email(payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )
        if await self._users.get_by_username(payload.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
            )

        user = User(
            email=payload.email.lower(),
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=UserRole.user,
            is_master=False,
            is_active=True,
        )
        await self._users.add(user)
        if invite is not None:
            invite.used_by_user_id = user.id
        from app.services.catalog import CatalogService

        await CatalogService(self._session).ensure_favourite_playlist(user.id)
        await self._session.commit()
        await self._session.refresh(user)
        return UserPublic.model_validate(user)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self._users.get_by_login(payload.login)
        if user is None or not verify_password(user.password_hash, payload.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
        tokens = await self._issue_tokens(user)
        if user.is_master:
            await self._audit.add(
                action="master.login",
                actor_id=user.id,
                target_kind="user",
                target_id=str(user.id),
            )
            await self._session.commit()
        return tokens

    async def refresh(self, refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._refresh.get_by_hash(token_hash)
        if stored is None or stored.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )
        if stored.expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
            )

        user = await self._users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
            )

        await self._refresh.revoke(stored)
        tokens = await self._issue_tokens(user)
        await self._session.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._refresh.get_by_hash(token_hash)
        if stored is not None and stored.revoked_at is None:
            await self._refresh.revoke(stored)
            await self._session.commit()

    async def update_me(self, user: User, payload: UpdateMeRequest) -> UserPublic:
        if payload.username is not None and payload.username != user.username:
            existing = await self._users.get_by_username(payload.username)
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
                )
            user.username = payload.username

        if payload.new_password is not None:
            if payload.current_password is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="current_password is required to set new_password",
                )
            if not verify_password(user.password_hash, payload.current_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password"
                )
            user.password_hash = hash_password(payload.new_password)

        user.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(user)
        return UserPublic.model_validate(user)

    async def _issue_tokens(self, user: User) -> TokenResponse:
        access_token, expires_in = create_access_token(user.id)
        refresh_value = generate_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_value),
            expires_at=datetime.now(UTC) + refresh_token_ttl(user),
        )
        await self._refresh.add(refresh)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_value,
            expires_in=expires_in,
        )


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._invites = InviteRepository(session)
        self._audit = AuditLogRepository(session)

    async def list_users(self) -> list[UserPublic]:
        users = await self._users.list_users()
        return [UserPublic.model_validate(user) for user in users]

    async def create_user(self, actor: User, payload: CreateUserRequest) -> UserPublic:
        if await self._users.get_by_email(payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )
        if await self._users.get_by_username(payload.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
            )

        user = User(
            email=payload.email.lower(),
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_master=False,
            is_active=True,
        )
        await self._users.add(user)
        await self._audit.add(
            action="admin.user.created",
            actor_id=actor.id,
            target_kind="user",
            target_id=str(user.id),
        )
        from app.services.catalog import CatalogService

        await CatalogService(self._session).ensure_favourite_playlist(user.id)
        await self._session.commit()
        await self._session.refresh(user)
        return UserPublic.model_validate(user)

    async def update_user(
        self, actor: User, user_id: uuid.UUID, payload: UpdateUserRequest
    ) -> UserPublic:
        user = await self._get_user_or_404(user_id)
        if user.is_master and user.id != actor.id and not actor.is_master:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify master account"
            )

        if payload.email is not None:
            user.email = payload.email.lower()
        if payload.username is not None:
            user.username = payload.username
        if payload.is_active is not None:
            if user.is_master and not payload.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Master account cannot be deactivated",
                )
            user.is_active = payload.is_active

        user.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(user)
        return UserPublic.model_validate(user)

    async def update_user_role(
        self,
        actor: User,
        user_id: uuid.UUID,
        payload: UpdateUserRoleRequest,
    ) -> UserPublic:
        user = await self._get_user_or_404(user_id)
        if user.is_master:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Cannot change master role"
            )
        user.role = payload.role
        user.updated_at = datetime.now(UTC)
        await self._audit.add(
            action="admin.user.role_changed",
            actor_id=actor.id,
            target_kind="user",
            target_id=str(user.id),
            metadata={"role": payload.role.value},
        )
        await self._session.commit()
        await self._session.refresh(user)
        return UserPublic.model_validate(user)

    async def delete_user(self, actor: User, user_id: uuid.UUID) -> None:
        user = await self._get_user_or_404(user_id)
        if user.is_master:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Master account cannot be deleted"
            )
        try:
            await self._users.delete(user)
            await self._audit.add(
                action="admin.user.deleted",
                actor_id=actor.id,
                target_kind="user",
                target_id=str(user_id),
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Master account cannot be deleted",
            ) from exc

    async def create_invite(self, actor: User, payload: CreateInviteRequest) -> Invite:
        expires_at = None
        if payload.expires_in_days is not None:
            expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days)
        invite = Invite(
            code=secrets.token_urlsafe(16),
            created_by_user_id=actor.id,
            expires_at=expires_at,
        )
        await self._invites.add(invite)
        await self._session.commit()
        await self._session.refresh(invite)
        return invite

    async def _get_user_or_404(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user


class MasterBootstrapService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._audit = AuditLogRepository(session)

    async def init_master(self, *, email: str, username: str, password: str) -> User:
        if await self._users.master_exists():
            raise RuntimeError("Master account already exists")

        user = User(
            email=email.lower(),
            username=username,
            password_hash=hash_password(password),
            role=UserRole.admin,
            is_master=True,
            is_active=True,
        )
        await self._users.add(user)
        await self._audit.add(
            action="master.created",
            actor_id=user.id,
            target_kind="user",
            target_id=str(user.id),
        )
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def reset_master_password(self, password: str) -> User:
        users = await self._users.list_users()
        master = next((user for user in users if user.is_master), None)
        if master is None:
            raise RuntimeError("Master account not found")

        master.password_hash = hash_password(password)
        master.updated_at = datetime.now(UTC)
        await self._audit.add(
            action="master.password_reset",
            actor_id=master.id,
            target_kind="user",
            target_id=str(master.id),
        )
        await self._session.commit()
        await self._session.refresh(master)
        return master
