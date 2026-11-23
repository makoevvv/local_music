from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.core.sync_db import sync_session
from app.models.catalog import Album, Artist, ArtistRole, Track, TrackArtist, TrackStatus
from app.schemas.upload import AlbumResolution
from app.services.metadata_enrichment import enrich_track_metadata


def _ready_track(
    *,
    title: str,
    artist_name: str,
    album: Album | None = None,
    mbid: str | None = None,
    cover_url_origin: str | None = None,
    metadata: dict[str, object] | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    with sync_session() as session:
        artist = Artist(name=artist_name, sort_name=artist_name)
        session.add(artist)
        session.flush()
        track = Track(
            title=title,
            album_id=album.id if album is not None else None,
            file_path="pending",
            status=TrackStatus.ready,
            mbid=mbid,
            cover_url_origin=cover_url_origin,
            metadata_=metadata or {"candidate_id": "search"},
        )
        session.add(track)
        session.flush()
        session.add(
            TrackArtist(
                track_id=track.id,
                artist_id=artist.id,
                role=ArtistRole.main,
                position=0,
            )
        )
        return track.id, artist.id


@pytest.mark.asyncio
async def test_search_download_uses_album_resolution() -> None:
    track_id, artist_id = _ready_track(
        title="Numb",
        artist_name="Linkin Park",
        cover_url_origin="https://i.ytimg.com/vi/numb/hqdefault.jpg",
    )
    decision = AlbumResolution(
        title="Meteora",
        release_group_mbid="rg-meteora",
        release_year=2003,
        is_single=False,
        unresolved=False,
        cover_url="https://coverartarchive.org/release-group/rg-meteora/front",
        recording_mbid="rec-numb",
    )

    with (
        patch("app.services.metadata_enrichment.resolve_album", return_value=decision) as resolve,
        patch("app.services.metadata_enrichment._fetch_lastfm_tags", return_value=[]),
    ):
        with sync_session() as session:
            enrich_track_metadata(session, track_id)
        resolve.assert_called_once_with(artist="Linkin Park", title="Numb", recording_mbid=None)

    with sync_session() as session:
        track = session.get(Track, track_id)
        assert track is not None
        assert track.album_id is not None
        album = session.get(Album, track.album_id)
        assert album is not None
        assert album.title == "Meteora"
        assert album.mbid == "rg-meteora"
        assert album.release_year == 2003
        assert album.is_single is False
        assert album.primary_artist_id == artist_id
        assert album.metadata_["cover_url"] == decision.cover_url
        assert track.mbid == "rec-numb"
        assert track.cover_url_origin == "https://i.ytimg.com/vi/numb/hqdefault.jpg"
        assert track.metadata_["candidate_id"] == "search"
        assert "album_unresolved" not in track.metadata_
        assert session.scalar(select(func.count()).select_from(Artist)) == 1


@pytest.mark.asyncio
async def test_search_download_reuses_album_and_marks_unresolved_or_single() -> None:
    with sync_session() as session:
        existing = Album(title="Meteora", mbid="rg-shared", release_year=2003, is_single=False)
        session.add(existing)
        session.flush()
        existing_id = existing.id

    reused_id, _ = _ready_track(title="Numb", artist_name="Linkin Park")
    unresolved_id, _ = _ready_track(title="Demo", artist_name="Demo Artist")
    single_id, _ = _ready_track(title="One More Light", artist_name="Linkin Park")

    reused = AlbumResolution(
        title="Meteora",
        release_group_mbid="rg-shared",
        release_year=2003,
        is_single=False,
        recording_mbid="rec-reused",
    )
    unresolved = AlbumResolution(title="Demo", unresolved=True, is_single=False)
    single = AlbumResolution(
        title="One More Light",
        release_group_mbid="rg-single",
        release_year=2017,
        is_single=True,
        recording_mbid="rec-single",
    )

    def _resolve(*, artist: str, title: str, recording_mbid: str | None) -> AlbumResolution:
        return {"Numb": reused, "Demo": unresolved, "One More Light": single}[title]

    with (
        patch("app.services.metadata_enrichment.resolve_album", side_effect=_resolve),
        patch("app.services.metadata_enrichment._fetch_lastfm_tags", return_value=[]),
        sync_session() as session,
    ):
        enrich_track_metadata(session, reused_id)
        enrich_track_metadata(session, unresolved_id)
        enrich_track_metadata(session, single_id)

    with sync_session() as session:
        reused_track = session.get(Track, reused_id)
        unresolved_track = session.get(Track, unresolved_id)
        single_track = session.get(Track, single_id)
        assert reused_track is not None and reused_track.album_id == existing_id
        assert unresolved_track is not None and unresolved_track.album_id is not None
        unresolved_album = session.get(Album, unresolved_track.album_id)
        assert unresolved_album is not None
        assert unresolved_album.title == "Demo"
        assert unresolved_album.is_single is False
        assert unresolved_album.mbid is None
        assert unresolved_track.metadata_["album_unresolved"] is True
        assert single_track is not None and single_track.album_id is not None
        single_album = session.get(Album, single_track.album_id)
        assert single_album is not None
        assert single_album.is_single is True
        assert single_album.mbid == "rg-single"
        assert session.scalar(select(func.count()).select_from(Album)) == 3


@pytest.mark.asyncio
async def test_search_download_keeps_existing_album() -> None:
    with sync_session() as session:
        album = Album(title="User Album", is_single=False)
        session.add(album)
        session.flush()
        album_id = album.id
    track_id, _ = _ready_track(title="Numb", artist_name="Linkin Park", album=album)

    with patch("app.services.metadata_enrichment.resolve_album") as resolve:
        with sync_session() as session:
            enrich_track_metadata(session, track_id)
        resolve.assert_not_called()

    with sync_session() as session:
        track = session.get(Track, track_id)
        assert track is not None
        assert track.album_id == album_id
