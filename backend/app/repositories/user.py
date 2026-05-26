from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.invite import Invite
from app.models.refresh_token import RefreshToken
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_login(self, login: str) -> User | None:
        result = await self._session.execute(
            select(User).where((User.email == login) | (User.username == login))
        )
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        result = await self._session.execute(select(User).order_by(User.created_at))
        return list(result.scalars().all())

    async def master_exists(self) -> bool:
        result = await self._session.execute(select(User.id).where(User.is_master.is_(True)).limit(1))
        return result.scalar_one_or_none() is not None

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def delete(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.flush()


class InviteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> Invite | None:
        result = await self._session.execute(select(Invite).where(Invite.code == code))
        return result.scalar_one_or_none()

    async def add(self, invite: Invite) -> Invite:
        self._session.add(invite)
        await self._session.flush()
        return invite


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def add(self, token: RefreshToken) -> RefreshToken:
        self._session.add(token)
        await self._session.flush()
        return token

    async def revoke(self, token: RefreshToken) -> None:
        from datetime import UTC, datetime

        token.revoked_at = datetime.now(UTC)


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        action: str,
        actor_id: uuid.UUID | None = None,
        target_kind: str | None = None,
        target_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_id=actor_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            metadata_=metadata or {},
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
