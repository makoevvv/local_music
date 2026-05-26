from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.catalog import CatalogService
from tests.conftest_auth import login


@pytest.fixture
def storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("app.core.config.settings.storage_local_path", str(tmp_path))
    return tmp_path


@pytest.fixture
async def sample_track(
    db_session: AsyncSession,
    regular_user: User,
    storage_dir: Path,
    tmp_path: Path,
) -> object:
    source = tmp_path / "sample.mp3"
    source.write_bytes(b"fake-audio-bytes-for-testing")
    return await CatalogService(db_session).import_local_track(
        source_file=source,
        title="Sample Track",
        artist_name="Sample Artist",
        album_title="Sample Album",
        added_by_user_id=regular_user.id,
    )


@pytest.mark.asyncio
async def test_list_tracks_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tracks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_and_get_track(
    client: AsyncClient,
    regular_user: User,
    sample_track: object,
) -> None:
    token = await login(client, "friend@example.com", "friend-password-123")

    list_response = await client.get(
        "/api/v1/tracks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Sample Track"
    assert body["items"][0]["artists"][0]["name"] == "Sample Artist"

    detail_response = await client.get(
        f"/api/v1/tracks/{sample_track.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["album"]["title"] == "Sample Album"


@pytest.mark.asyncio
async def test_stream_track(
    client: AsyncClient,
    regular_user: User,
    sample_track: object,
) -> None:
    token = await login(client, "friend@example.com", "friend-password-123")
    response = await client.get(
        f"/api/v1/tracks/{sample_track.id}/stream",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.content == b"fake-audio-bytes-for-testing"


@pytest.mark.asyncio
async def test_like_adds_track_to_favourite_playlist(
    client: AsyncClient,
    regular_user: User,
    sample_track: object,
) -> None:
    token = await login(client, "friend@example.com", "friend-password-123")

    like_response = await client.put(
        f"/api/v1/tracks/{sample_track.id}/like",
        headers={"Authorization": f"Bearer {token}"},
        json={"sentiment": "like"},
    )
    assert like_response.status_code == 204

    playlists_response = await client.get(
        "/api/v1/playlists",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert playlists_response.status_code == 200
    playlists = playlists_response.json()
    favourite = next(item for item in playlists if item["is_favourite"])
    assert favourite["name"] == "Любимое"
    assert favourite["track_count"] == 1

    detail_response = await client.get(
        f"/api/v1/playlists/{favourite['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["tracks"][0]["track"]["id"] == str(sample_track.id)


@pytest.mark.asyncio
async def test_playlist_crud(
    client: AsyncClient,
    regular_user: User,
    sample_track: object,
) -> None:
    token = await login(client, "friend@example.com", "friend-password-123")

    create_response = await client.post(
        "/api/v1/playlists",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Road Trip", "is_public": False},
    )
    assert create_response.status_code == 201
    playlist_id = create_response.json()["id"]

    add_response = await client.post(
        f"/api/v1/playlists/{playlist_id}/tracks",
        headers={"Authorization": f"Bearer {token}"},
        json={"track_ids": [str(sample_track.id)]},
    )
    assert add_response.status_code == 200
    assert add_response.json()["track_count"] == 1

    delete_response = await client.delete(
        f"/api/v1/playlists/{playlist_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_reference_data_is_seeded(client: AsyncClient, master_user: User) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")

    genres_response = await client.get(
        "/api/v1/genres",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert genres_response.status_code == 200
    genres = genres_response.json()
    assert len(genres) >= 1
    assert "slug" in genres[0]

    languages_response = await client.get(
        "/api/v1/languages",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert languages_response.status_code == 200
    languages = languages_response.json()
    assert any(item["code"] == "ru" for item in languages)


@pytest.mark.asyncio
async def test_start_play_and_heartbeat(
    client: AsyncClient,
    regular_user: User,
    sample_track: object,
) -> None:
    token = await login(client, "friend@example.com", "friend-password-123")

    play_response = await client.post(
        f"/api/v1/tracks/{sample_track.id}/play",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert play_response.status_code == 201
    play_id = play_response.json()["play_id"]

    heartbeat_response = await client.post(
        f"/api/v1/plays/{play_id}/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={"listened_seconds": 42, "completed": False},
    )
    assert heartbeat_response.status_code == 204
