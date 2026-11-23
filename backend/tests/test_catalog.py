from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Album, Artist, Track, TrackArtist
from app.models.user import User
from app.services.artists import get_or_create_artist
from app.services.catalog import CatalogService
from app.services.track_sources import build_track_source
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


@pytest.mark.asyncio
async def test_import_reuses_artist_by_name(
    db_session: AsyncSession,
    regular_user: User,
    storage_dir: Path,
    tmp_path: Path,
) -> None:
    service = CatalogService(db_session)
    first_file = tmp_path / "first.mp3"
    second_file = tmp_path / "second.mp3"
    first_file.write_bytes(b"audio-first")
    second_file.write_bytes(b"audio-second")

    first = await service.import_local_track(
        source_file=first_file,
        title="First",
        artist_name="Sample Artist",
        added_by_user_id=regular_user.id,
    )
    second = await service.import_local_track(
        source_file=second_file,
        title="Second",
        artist_name="  sample   artist ",
        added_by_user_id=regular_user.id,
    )

    artists = (await db_session.scalars(select(Artist))).all()
    assert len(artists) == 1
    assert artists[0].name == "Sample Artist"
    links = (await db_session.scalars(select(TrackArtist.artist_id))).all()
    assert set(links) == {artists[0].id}
    assert first.id != second.id
    assert storage_dir.is_dir()


@pytest.mark.asyncio
async def test_get_or_create_artist_matches_mbid_before_a_different_name(
    db_session: AsyncSession,
) -> None:
    first = await get_or_create_artist(db_session, "Linkin Park", mbid="mb-1")
    reused = await get_or_create_artist(db_session, "Other Name", mbid="mb-1")
    same_name = await get_or_create_artist(db_session, "linkin park")
    other_mbid = await get_or_create_artist(db_session, "Linkin Park", mbid="mb-2")
    await db_session.commit()

    assert reused.id == first.id
    assert same_name.id == first.id
    assert other_mbid.id != first.id
    assert other_mbid.mbid == "mb-2"


@pytest.mark.asyncio
async def test_track_list_returns_stored_cover(
    client: AsyncClient,
    regular_user: User,
    sample_track: Track,
    storage_dir: Path,
    db_session: AsyncSession,
) -> None:
    album = await db_session.get(Album, sample_track.album_id)
    assert album is not None
    album.metadata_ = {"cover_url": "https://coverartarchive.org/release/1/front"}
    sample_track.cover_url_origin = "https://i.ytimg.com/vi/x/hqdefault.jpg"
    await db_session.commit()

    token = await login(client, "friend@example.com", "friend-password-123")
    headers = {"Authorization": f"Bearer {token}"}
    listed = await client.get("/api/v1/tracks", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["cover_url"] == "https://coverartarchive.org/release/1/front"

    cover = storage_dir / "covers" / "art.jpg"
    cover.parent.mkdir(parents=True)
    cover.write_bytes(b"\xff\xd8\xff-cover")
    album.cover_path = "covers/art.jpg"
    await db_session.commit()

    listed = await client.get("/api/v1/tracks", headers=headers)
    assert listed.json()["items"][0]["cover_url"] == f"/api/v1/tracks/{sample_track.id}/cover"
    cover_response = await client.get(f"/api/v1/tracks/{sample_track.id}/cover", headers=headers)
    assert cover_response.status_code == 200
    assert cover_response.content == b"\xff\xd8\xff-cover"

    album.cover_path = "/etc/passwd"
    await db_session.commit()
    blocked = await client.get(f"/api/v1/tracks/{sample_track.id}/cover", headers=headers)
    assert blocked.status_code == 404
    listed = await client.get("/api/v1/tracks", headers=headers)
    assert listed.json()["items"][0]["cover_url"] == "https://coverartarchive.org/release/1/front"


@pytest.mark.asyncio
async def test_track_source_identity_is_unique(
    db_session: AsyncSession,
    regular_user: User,
    storage_dir: Path,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "unique.mp3"
    audio.write_bytes(b"unique-audio")
    track = await CatalogService(db_session).import_local_track(
        source_file=audio,
        title="Unique",
        artist_name="Unique Artist",
        added_by_user_id=regular_user.id,
    )
    db_session.add(
        build_track_source(
            track_id=track.id,
            source_kind="youtube",
            source_id="abc123",
            source_url="https://youtu.be/abc123",
        )
    )
    db_session.add(
        build_track_source(
            track_id=track.id,
            source_kind="youtube",
            source_id="def456",
            source_url="https://youtu.be/def456",
        )
    )
    await db_session.flush()

    db_session.add(
        build_track_source(
            track_id=track.id,
            source_kind="youtube",
            source_id="abc123",
            source_url="https://www.youtube.com/watch?v=abc123",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_null_source_id_is_not_stored_twice(
    db_session: AsyncSession,
    regular_user: User,
    storage_dir: Path,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "null-id.mp3"
    audio.write_bytes(b"null-id-audio")
    track = await CatalogService(db_session).import_local_track(
        source_file=audio,
        title="Null Id",
        artist_name="Null Artist",
        added_by_user_id=regular_user.id,
    )
    db_session.add(
        build_track_source(
            track_id=track.id,
            source_kind="youtube",
            source_id=None,
            source_url="https://youtu.be/no-id",
        )
    )
    await db_session.flush()
    db_session.add(
        build_track_source(
            track_id=track.id,
            source_kind="user_upload",
            source_id=None,
            original_filename="again.mp3",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
