from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.vibe import UserAffinity
from app.services.catalog import CatalogService
from tests.conftest_auth import login


@pytest.fixture
def storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("app.core.config.settings.storage_local_path", str(tmp_path))
    return tmp_path


async def _track(
    db_session: AsyncSession,
    user: User,
    storage_dir: Path,
    *,
    title: str,
    artist: str,
    bpm: float,
    energy: float,
    valence: float,
) -> str:
    source = storage_dir / f"{title}.mp3"
    source.write_bytes(f"fake-audio-{title}-{artist}".encode())
    track = await CatalogService(db_session).import_local_track(
        source_file=source,
        title=title,
        artist_name=artist,
        added_by_user_id=user.id,
    )
    track.bpm = bpm
    track.energy = energy
    track.valence = valence
    await db_session.commit()
    return str(track.id)


@pytest.mark.asyncio
async def test_calm_session_keeps_only_calm_tracks(
    client: AsyncClient,
    db_session: AsyncSession,
    regular_user: User,
    storage_dir: Path,
) -> None:
    calm_id = await _track(
        db_session,
        regular_user,
        storage_dir,
        title="Quiet",
        artist="Quiet Artist",
        bpm=72,
        energy=0.2,
        valence=0.5,
    )
    await _track(
        db_session,
        regular_user,
        storage_dir,
        title="Loud",
        artist="Loud Artist",
        bpm=150,
        energy=0.9,
        valence=0.8,
    )
    token = await login(client, "friend@example.com", "friend-password-123")
    response = await client.post(
        "/api/v1/vibe/session",
        headers={"Authorization": f"Bearer {token}"},
        json={"mood": "calm", "mode": "mixed"},
    )
    assert response.status_code == 201
    body = response.json()
    assert [item["id"] for item in body["queue"]] == [calm_id]


@pytest.mark.asyncio
async def test_dislike_drops_track_from_the_next_batch(
    client: AsyncClient,
    db_session: AsyncSession,
    regular_user: User,
    storage_dir: Path,
) -> None:
    first = await _track(
        db_session,
        regular_user,
        storage_dir,
        title="One",
        artist="Artist One",
        bpm=100,
        energy=0.5,
        valence=0.5,
    )
    second = await _track(
        db_session,
        regular_user,
        storage_dir,
        title="Two",
        artist="Artist Two",
        bpm=100,
        energy=0.5,
        valence=0.5,
    )
    token = await login(client, "friend@example.com", "friend-password-123")
    headers = {"Authorization": f"Bearer {token}"}
    started = await client.post(
        "/api/v1/vibe/session",
        headers=headers,
        json={"mood": "neutral", "mode": "mixed"},
    )
    assert started.status_code == 201
    session_id = started.json()["session_id"]
    queued = {item["id"] for item in started.json()["queue"]}
    assert queued == {first, second}

    feedback = await client.post(
        f"/api/v1/vibe/{session_id}/feedback",
        headers=headers,
        json={"track_id": first, "action": "dislike"},
    )
    assert feedback.status_code == 204

    nxt = await client.post(f"/api/v1/vibe/{session_id}/next", headers=headers)
    assert nxt.status_code == 200
    assert [item["id"] for item in nxt.json()["queue"]] == [second]

    affinity = (
        await db_session.scalars(
            select(UserAffinity).where(
                UserAffinity.user_id == regular_user.id,
                UserAffinity.target_kind == "artist",
            )
        )
    ).all()
    assert len(affinity) == 1
    assert affinity[0].score == -5


@pytest.mark.asyncio
async def test_presets_round_trip(
    client: AsyncClient,
    regular_user: User,
) -> None:
    token = await login(client, "friend@example.com", "friend-password-123")
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/vibe/presets",
        headers=headers,
        json={"name": "Night", "mood": "focus", "mode": "discover", "no_lyrics": True},
    )
    assert created.status_code == 201
    assert created.json()["settings"]["mood"] == "focus"

    listed = await client.get("/api/v1/vibe/presets", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Night"
