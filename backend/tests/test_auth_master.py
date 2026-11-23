from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.invite import Invite
from app.models.user import User, UserRole
from app.repositories.user import InviteRepository, UserRepository
from app.services.auth import MasterBootstrapService
from tests.conftest_auth import login


@pytest.mark.asyncio
async def test_register_with_invite(
    client: AsyncClient, db_session: AsyncSession, master_user: User
) -> None:
    invite = Invite(code="register-me-please", created_by_user_id=master_user.id)
    await InviteRepository(db_session).add(invite)
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newbie@example.com",
            "username": "newbie",
            "password": "newbie-password",
            "invite_code": "register-me-please",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newbie@example.com"
    assert body["is_master"] is False


@pytest.mark.asyncio
async def test_login_and_me(client: AsyncClient, master_user: User) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["is_master"] is True


@pytest.mark.asyncio
async def test_delete_master_returns_403(client: AsyncClient, master_user: User) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    response = await client.delete(
        f"/api/v1/admin/users/{master_user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.asyncio
async def test_change_user_role_requires_master(
    client: AsyncClient,
    master_user: User,
    regular_user: User,
) -> None:
    friend_token = await login(client, "friend@example.com", "friend-password-123")
    response = await client.patch(
        f"/api/v1/admin/users/{regular_user.id}/role",
        headers={"Authorization": f"Bearer {friend_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 403

    master_token = await login(client, "owner@example.com", "owner-password-123")
    response = await client.patch(
        f"/api/v1/admin/users/{regular_user.id}/role",
        headers={"Authorization": f"Bearer {master_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_is_master_flag_is_immutable(db_session: AsyncSession, master_user: User) -> None:
    other = User(
        email="other@example.com",
        username="other",
        password_hash=hash_password("other-password-123"),
        role=UserRole.user,
        is_master=False,
        is_active=True,
    )
    await UserRepository(db_session).add(other)
    await db_session.flush()

    other.is_master = True
    with pytest.raises(Exception, match="is_master flag is immutable"):
        await db_session.flush()


@pytest.mark.asyncio
async def test_login_rejects_unknown_password(client: AsyncClient, master_user: User) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": "owner@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_logout_revokes_it(
    client: AsyncClient, regular_user: User
) -> None:
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"login": "friend@example.com", "password": "friend-password-123"},
    )
    assert logged_in.status_code == 200
    refresh_token = logged_in.json()["refresh_token"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refreshed.status_code == 200
    new_refresh = refreshed.json()["refresh_token"]
    assert new_refresh != refresh_token

    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": new_refresh},
    )
    assert logout.status_code == 204

    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert reused.status_code == 401


@pytest.mark.asyncio
async def test_update_me_changes_username_and_password(
    client: AsyncClient, regular_user: User
) -> None:
    token = await login(client, "friend@example.com", "friend-password-123")
    renamed = await client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "friend-renamed"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["username"] == "friend-renamed"

    changed = await client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "friend-password-123",
            "new_password": "friend-password-456",
        },
    )
    assert changed.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"login": "friend-renamed", "password": "friend-password-123"},
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"login": "friend-renamed", "password": "friend-password-456"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_register_rejects_unknown_invite(client: AsyncClient, master_user: User) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "stranger@example.com",
            "username": "stranger",
            "password": "stranger-password",
            "invite_code": "missing-invite",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_master_creates_lists_deactivates_and_invites(
    client: AsyncClient, master_user: User, regular_user: User
) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "extra@example.com",
            "username": "extra",
            "password": "extra-password-123",
            "role": "user",
        },
    )
    assert created.status_code == 201
    created_id = created.json()["id"]

    listed = await client.get("/api/v1/admin/users", headers=headers)
    assert listed.status_code == 200
    assert any(item["id"] == created_id for item in listed.json())

    deactivated = await client.patch(
        f"/api/v1/admin/users/{regular_user.id}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    blocked = await client.post(
        "/api/v1/auth/login",
        json={"login": "friend@example.com", "password": "friend-password-123"},
    )
    assert blocked.status_code == 403

    invite = await client.post(
        "/api/v1/admin/invites",
        headers=headers,
        json={"expires_in_days": 3},
    )
    assert invite.status_code == 201
    assert invite.json()["code"]


@pytest.mark.asyncio
async def test_only_one_master_allowed(db_session: AsyncSession) -> None:
    service = MasterBootstrapService(db_session)
    await service.init_master(
        email="first@example.com",
        username="first",
        password="first-password-123",
    )
    with pytest.raises(RuntimeError, match="Master account already exists"):
        await service.init_master(
            email="second@example.com",
            username="second",
            password="second-password-123",
        )
