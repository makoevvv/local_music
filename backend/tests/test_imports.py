from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Artist, ArtistRole, Playlist, Track, TrackArtist, TrackStatus
from app.models.imports import ImportItem, ImportJob
from app.schemas.upload import CandidateSource
from app.services.imports.crypto import decrypt_token, encrypt_token
from app.services.imports.parser import parse_import_payload
from tests.conftest_auth import login

CSV = """title,artist,album,isrc,duration_seconds,playlist
Known Song,Known Artist,Album,ISRC123,180,Mix
New Song,New Artist,Album,,200,Mix
Weak Song,Weak Artist,Album,,210,Mix
"""


@pytest.mark.no_db
def test_parse_csv_and_soundiiz_json() -> None:
    rows = parse_import_payload("lib.csv", CSV.encode())
    assert [row.title for row in rows] == ["Known Song", "New Song", "Weak Song"]
    assert rows[0].isrc == "ISRC123"
    payload = b'{"playlists":[{"name":"Night","tracks":[{"title":"A","artist":"B"}]}]}'
    parsed = parse_import_payload("export.json", payload)
    assert parsed[0].playlist_name == "Night"
    assert parsed[0].title == "A"


@pytest.mark.no_db
def test_token_roundtrip() -> None:
    sealed = encrypt_token("secret-token")
    assert decrypt_token(sealed) == "secret-token"
    assert b"secret-token" not in sealed


def _candidate(title: str, match: float) -> CandidateSource:
    return CandidateSource(
        kind="youtube",
        source_id=title.lower().replace(" ", ""),
        url=f"https://www.youtube.com/watch?v={title}",
        match=match,
        duration_delta=0,
        title=title,
        channel="channel",
    )


def _search(query: str, **_: object) -> list[CandidateSource]:
    if "New Song" in query:
        return [_candidate("New Song", 0.95)]
    if "Weak Song" in query:
        return [_candidate("Weak Song", 0.4)]
    return []


def _download(session, *, user_id, candidate, title, artist) -> uuid.UUID:  # type: ignore[no-untyped-def]
    track = Track(
        title=title,
        file_path="pending",
        status=TrackStatus.ready,
        added_by_user_id=user_id,
        audio_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        metadata_={"imported_from_external": True},
    )
    session.add(track)
    session.flush()
    return track.id


@pytest.mark.asyncio
async def test_file_import_resolves_links_and_is_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    master_user: object,
) -> None:
    artist = Artist(name="Known Artist", sort_name="Known Artist")
    known = Track(
        title="Known Song",
        file_path="pending",
        status=TrackStatus.ready,
        isrc="ISRC123",
        audio_sha256="c" * 64,
    )
    db_session.add_all([artist, known])
    await db_session.flush()
    db_session.add(
        TrackArtist(track_id=known.id, artist_id=artist.id, role=ArtistRole.main, position=0)
    )
    await db_session.commit()
    known_id = known.id
    token = await login(client, "owner@example.com", "owner-password-123")

    def _enqueue(job_id: str) -> None:
        from app.services.imports.pipeline import run_import_job

        run_import_job(job_id)

    with (
        patch("app.services.imports.jobs.enqueue_import", side_effect=_enqueue),
        patch("app.services.imports.pipeline.find_public_candidates", side_effect=_search),
        patch("app.services.imports.pipeline.schedule_public_download", side_effect=_download),
    ):
        first = await client.post(
            "/api/v1/import/file",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("lib.csv", CSV.encode(), "text/csv")},
            data={"mode": "add", "auto_threshold": "0.85", "create_missing": "true"},
        )
        assert first.status_code == 201, first.text
        body = first.json()
        assert body["status"] == "completed"
        assert body["resolved_tracks"] == 2
        assert body["ambiguous_tracks"] == 1

        second = await client.post(
            "/api/v1/import/file",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("lib.csv", CSV.encode(), "text/csv")},
            data={"mode": "add"},
        )
        assert second.status_code == 201
        assert second.json()["id"] == body["id"]

    db_session.expire_all()
    items = (
        await db_session.scalars(
            select(ImportItem).where(ImportItem.job_id == uuid.UUID(body["id"]))
        )
    ).all()
    by_title = {item.title: item for item in items}
    assert by_title["Known Song"].status == "resolved"
    assert by_title["Known Song"].matched_track_id == known_id
    assert by_title["New Song"].status == "resolved"
    assert by_title["Weak Song"].status == "ambiguous"
    playlists = (await db_session.scalars(select(Playlist))).all()
    assert any(playlist.name == "Mix" for playlist in playlists)
    job = await db_session.get(ImportJob, uuid.UUID(body["id"]))
    assert job is not None
    assert job.source_meta["fingerprint"]


@pytest.mark.asyncio
async def test_spotify_connect_reports_unconfigured(
    client: AsyncClient, master_user: object
) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    response = await client.get(
        "/api/v1/import/spotify/connect",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503
