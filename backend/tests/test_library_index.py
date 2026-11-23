from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.catalog import Track, TrackSource
from app.services.catalog import CatalogService
from app.services.library_index import ExportOptions, LibraryIndexService
from tests.conftest_auth import login


@pytest.mark.asyncio
async def test_import_local_track_writes_track_source(
    db_session: AsyncSession,
    master_user: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path / "storage"))
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"ID3fake-audio-bytes-for-sha")

    track = await CatalogService(db_session).import_local_track(
        source_file=audio,
        title="Local Song",
        artist_name="Local Artist",
        added_by_user_id=master_user.id,  # type: ignore[attr-defined]
    )

    sources = (
        await db_session.scalars(select(TrackSource).where(TrackSource.track_id == track.id))
    ).all()
    assert len(sources) == 1
    assert sources[0].source_kind == "user_upload"
    assert sources[0].original_filename == "song.mp3"
    assert sources[0].recovery_priority == 60
    assert track.source_kind == "user_upload"


@pytest.mark.asyncio
async def test_index_export_import_roundtrip(
    db_session: AsyncSession,
    master_user: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "storage_local_path", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "exports_local_path", str(tmp_path / "exports"))

    audio = tmp_path / "roundtrip.mp3"
    audio.write_bytes(b"roundtrip-audio-content-123")
    track = await CatalogService(db_session).import_local_track(
        source_file=audio,
        title="Roundtrip",
        artist_name="Artist",
        album_title="Album",
        added_by_user_id=master_user.id,  # type: ignore[attr-defined]
    )

    export_path = tmp_path / "exports" / "library-test.tar.gz"
    service = LibraryIndexService(db_session)
    exported = await service.export_index(
        ExportOptions(out=export_path, minimal=False, no_plays=True)
    )
    assert exported.track_count == 1
    assert export_path.is_file()

    # Remove track to simulate clean import target (keep master user).
    await db_session.execute(delete(Track).where(Track.id == track.id))
    await db_session.commit()

    imported = await service.import_index(export_path, mode="skip-existing")
    assert imported.imported_tracks == 1

    restored = await db_session.get(
        Track,
        track.id,
        options=(selectinload(Track.sources),),
    )
    assert restored is not None
    assert restored.title == "Roundtrip"
    assert restored.metadata_.get("missing_file") is True
    assert len(restored.sources) >= 1
    assert restored.sources[0].source_kind == "user_upload"


@pytest.mark.asyncio
async def test_from_candidate_creates_track_source(
    client: AsyncClient,
    db_session: AsyncSession,
    master_user: object,
) -> None:
    from unittest.mock import patch

    from app.services.ytdlp import YtdlpSearchResult

    token = await login(client, "owner@example.com", "owner-password-123")
    mock_results = [
        YtdlpSearchResult(
            source_kind="youtube",
            source_id="src42",
            title="Indexed Song",
            artist="Indexed Artist",
            duration_seconds=120,
            thumbnail_url=None,
            source_url="https://www.youtube.com/watch?v=src42",
            tier=2,
            license=None,
            raw={},
        )
    ]

    with patch("app.services.search.search_entries", return_value=mock_results):
        search_response = await client.post(
            "/api/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "indexed", "limit": 5},
        )
    candidate_id = search_response.json()["items"][0]["candidate_id"]

    with patch("app.services.sourcing.get_queue") as queue_mock:
        queue_mock.return_value.enqueue.return_value = None
        response = await client.post(
            "/api/v1/tracks/from-candidate",
            headers={"Authorization": f"Bearer {token}"},
            json={"candidate_id": candidate_id},
        )

    assert response.status_code == 201
    track_id = response.json()["track_id"]
    sources = (
        await db_session.scalars(select(TrackSource).where(TrackSource.track_id == track_id))
    ).all()
    assert len(sources) == 1
    assert sources[0].source_kind == "youtube"
    assert sources[0].source_id == "src42"
    assert sources[0].recovery_priority == 30


@pytest.mark.asyncio
async def test_admin_library_health_and_minimal_export(
    client: AsyncClient,
    master_user: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "exports_local_path", str(tmp_path / "exports"))
    token = await login(client, "owner@example.com", "owner-password-123")

    health = await client.get(
        "/api/v1/admin/library/health",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert health.status_code == 200
    body = health.json()
    assert "missing_files" in body
    assert "sources_by_status" in body

    export = await client.post(
        "/api/v1/admin/index/export",
        headers={"Authorization": f"Bearer {token}"},
        json={"minimal": True, "filename": "health-export.jsonl.gz"},
    )
    assert export.status_code == 200
    assert export.json()["status"] == "completed"
    assert (tmp_path / "exports" / "health-export.jsonl.gz").is_file()

    listing = await client.get(
        "/api/v1/admin/index/exports",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listing.status_code == 200
    assert any(item["filename"] == "health-export.jsonl.gz" for item in listing.json())
