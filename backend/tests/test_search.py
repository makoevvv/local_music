from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Artist, Track
from app.services.ytdlp import YtdlpSearchResult
from tests.conftest_auth import login


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/search", json={"query": "test song", "limit": 5})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_returns_candidates(client: AsyncClient, master_user: object) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    mock_results = [
        YtdlpSearchResult(
            source_kind="youtube",
            source_id="abc123",
            title="Test Song",
            artist="Test Artist",
            duration_seconds=200,
            thumbnail_url="https://example.com/thumb.jpg",
            source_url="https://www.youtube.com/watch?v=abc123",
            tier=2,
            license=None,
            raw={},
        )
    ]

    with patch("app.services.search.search_entries", return_value=mock_results):
        response = await client.post(
            "/api/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "Test Artist Test Song", "limit": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is False
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Test Song"
    assert body["items"][0]["source_kind"] == "youtube"


@pytest.mark.asyncio
async def test_from_candidate_creates_downloading_track(
    client: AsyncClient,
    master_user: object,
) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    mock_results = [
        YtdlpSearchResult(
            source_kind="youtube",
            source_id="xyz789",
            title="Candidate Song",
            artist="Candidate Artist",
            duration_seconds=180,
            thumbnail_url=None,
            source_url="https://www.youtube.com/watch?v=xyz789",
            tier=2,
            license=None,
            raw={},
        )
    ]

    with patch("app.services.search.search_entries", return_value=mock_results):
        search_response = await client.post(
            "/api/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "candidate", "limit": 5},
        )
    candidate_id = search_response.json()["items"][0]["candidate_id"]

    with patch("app.services.sourcing.get_queue") as queue_mock:
        queue = queue_mock.return_value
        response = await client.post(
            "/api/v1/tracks/from-candidate",
            headers={"Authorization": f"Bearer {token}"},
            json={"candidate_id": candidate_id},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "downloading"
    queue.enqueue.assert_called_once()

    status_response = await client.get(
        f"/api/v1/tracks/{body['track_id']}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "downloading"


@pytest.mark.asyncio
async def test_from_candidate_unknown_returns_404(client: AsyncClient, master_user: object) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    response = await client.post(
        "/api/v1/tracks/from-candidate",
        headers={"Authorization": f"Bearer {token}"},
        json={"candidate_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def _candidate(source_id: str, title: str) -> YtdlpSearchResult:
    return YtdlpSearchResult(
        source_kind="youtube",
        source_id=source_id,
        title=title,
        artist="Same Artist",
        duration_seconds=180,
        thumbnail_url="https://i.ytimg.com/vi/same/hqdefault.jpg",
        source_url=f"https://www.youtube.com/watch?v={source_id}",
        tier=2,
        license=None,
        raw={},
    )


@pytest.mark.asyncio
async def test_from_candidate_reuses_existing_artist(
    client: AsyncClient,
    db_session: AsyncSession,
    master_user: object,
) -> None:
    token = await login(client, "owner@example.com", "owner-password-123")
    headers = {"Authorization": f"Bearer {token}"}

    with patch(
        "app.services.search.search_entries",
        side_effect=[[_candidate("aaa111", "One")], [_candidate("bbb222", "Two")]],
    ):
        first_search = await client.post(
            "/api/v1/search",
            headers=headers,
            json={"query": "Same Artist One", "limit": 5},
        )
        second_search = await client.post(
            "/api/v1/search",
            headers=headers,
            json={"query": "Same Artist Two", "limit": 5},
        )

    first_id = first_search.json()["items"][0]["candidate_id"]
    second_id = second_search.json()["items"][0]["candidate_id"]
    with patch("app.services.sourcing.get_queue") as queue_mock:
        queue_mock.return_value.enqueue.return_value = None
        first = await client.post(
            "/api/v1/tracks/from-candidate",
            headers=headers,
            json={"candidate_id": first_id},
        )
        second = await client.post(
            "/api/v1/tracks/from-candidate",
            headers=headers,
            json={"candidate_id": second_id},
        )

    assert first.status_code == 201
    assert second.status_code == 201
    artists = (await db_session.scalars(select(Artist))).all()
    tracks = (await db_session.scalars(select(Track))).all()
    assert [artist.name for artist in artists] == ["Same Artist"]
    assert {track.title for track in tracks} == {"One", "Two"}
    assert tracks[0].cover_url_origin == "https://i.ytimg.com/vi/same/hqdefault.jpg"
