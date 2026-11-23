from __future__ import annotations

import io
import json
import struct
import wave
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.catalog import Track, TrackSource
from app.schemas.upload import (
    AlbumResolution,
    CandidateSource,
    UploadSuggestions,
    VerificationResult,
)
from tests.conftest_auth import login


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"".join(struct.pack("<h", 0) for _ in range(8000)))
    return buffer.getvalue()


def _verification(level: str = "high") -> VerificationResult:
    return VerificationResult(
        trust_level=level,  # type: ignore[arg-type]
        score=0.95 if level == "high" else 0.3,
        suggestions=UploadSuggestions(
            title="Uploaded Song", artist="Uploaded Artist", album="Real Album"
        ),
        sources_verification=["heuristics"],
        candidate_sources=[
            CandidateSource(
                kind="youtube",
                source_id="abc123",
                url="https://www.youtube.com/watch?v=abc123",
                match=0.91,
                duration_delta=0,
                title="Uploaded Song",
                channel="Uploaded Artist",
            )
        ],
        primary_source_index=0,
        album_resolution=AlbumResolution(
            title="Real Album",
            release_group_mbid="rg-real",
            release_year=2001,
            is_single=False,
            unresolved=False,
        ),
        recording_mbid=None,
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_upload_confirm_writes_user_and_public_sources(
    client: AsyncClient,
    db_session: AsyncSession,
    master_user: object,
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path))
    token = await login(client, "owner@example.com", "owner-password-123")
    meta = {
        "title": "Uploaded Song",
        "artists": [{"name": "Uploaded Artist", "role": "main"}],
    }

    with (
        patch("app.services.uploads.build_verification", return_value=_verification()),
        patch("app.services.uploads.source_fingerprint_ok", return_value=True),
        patch("app.services.uploads._schedule_cleanup"),
    ):
        created = await client.post(
            "/api/v1/tracks/upload",
            headers=_auth(token),
            files={"file": ("song.wav", _wav_bytes(), "audio/wav")},
            data={"meta": json.dumps(meta)},
        )
        assert created.status_code == 201, created.text
        upload_id = created.json()["upload_id"]

        verified = await client.get(
            f"/api/v1/tracks/upload/{upload_id}/verify",
            headers=_auth(token),
            params={"meta": json.dumps(meta)},
        )
        assert verified.status_code == 200, verified.text
        body = verified.json()
        assert body["trust_level"] == "high"
        assert body["candidate_sources"][0]["source_id"] == "abc123"

        confirmed = await client.post(
            f"/api/v1/tracks/upload/{upload_id}/confirm",
            headers=_auth(token),
            json={
                "meta": meta,
                "accept_suggestions": False,
                "force": False,
                "selected_source_ids": ["youtube:abc123"],
                "primary_source_id": "youtube:abc123",
            },
        )

    assert confirmed.status_code == 200, confirmed.text
    payload = confirmed.json()
    assert payload["already_exists"] is False
    assert payload["rejected_source_ids"] == []

    db_session.expire_all()
    track = await db_session.get(Track, payload["track_id"])
    assert track is not None
    assert track.title == "Uploaded Song"
    assert track.status.value == "ready"
    assert track.source_kind == "youtube"
    sources = list(
        (
            await db_session.scalars(select(TrackSource).where(TrackSource.track_id == track.id))
        ).all()
    )
    kinds = {item.source_kind: item.recovery_priority for item in sources}
    assert kinds["user_upload"] == 100
    assert kinds["youtube"] == 10


@pytest.mark.asyncio
async def test_low_trust_requires_force(
    client: AsyncClient,
    master_user: object,
    tmp_path: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path))
    token = await login(client, "owner@example.com", "owner-password-123")
    meta = {"title": "Maybe", "artists": [{"name": "Someone", "role": "main"}]}
    with (
        patch("app.services.uploads.build_verification", return_value=_verification("low")),
        patch("app.services.uploads._schedule_cleanup"),
    ):
        created = await client.post(
            "/api/v1/tracks/upload",
            headers=_auth(token),
            files={"file": ("song.wav", _wav_bytes(), "audio/wav")},
            data={"meta": json.dumps(meta)},
        )
        upload_id = created.json()["upload_id"]
        await client.get(
            f"/api/v1/tracks/upload/{upload_id}/verify",
            headers=_auth(token),
            params={"meta": json.dumps(meta)},
        )
        rejected = await client.post(
            f"/api/v1/tracks/upload/{upload_id}/confirm",
            headers=_auth(token),
            json={"meta": meta, "force": False},
        )
    assert rejected.status_code == 409


@pytest.mark.asyncio
async def test_upload_rejects_unknown_extension(
    client: AsyncClient,
    master_user: object,
) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    response = await client.post(
        "/api/v1/tracks/upload",
        headers=_auth(token),
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
