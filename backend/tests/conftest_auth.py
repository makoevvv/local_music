from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.invite import Invite
from app.models.user import User, UserRole
from app.repositories.user import InviteRepository, UserRepository


@pytest.fixture
async def master_user(db_session: AsyncSession) -> User:
    user = User(
        email="owner@example.com",
        username="owner",
        password_hash=hash_password("owner-password-123"),
        role=UserRole.admin,
        is_master=True,
        is_active=True,
    )
    await UserRepository(db_session).add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def regular_user(db_session: AsyncSession, master_user: User) -> User:
    invite = Invite(code="test-invite-code", created_by_user_id=master_user.id)
    await InviteRepository(db_session).add(invite)
    user = User(
        email="friend@example.com",
        username="friend",
        password_hash=hash_password("friend-password-123"),
        role=UserRole.user,
        is_master=False,
        is_active=True,
    )
    await UserRepository(db_session).add(user)
    invite.used_by_user_id = user.id
    await db_session.flush()
    return user


async def login(client: AsyncClient, login: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": login, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]
