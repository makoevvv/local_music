from __future__ import annotations

import pytest

from app.schemas.upload import AlbumResolution
from app.services.album_resolution import decision_from_releases, unresolved_album
from app.services.chromaprint import fingerprint_similarity
from app.services.source_matching.score import is_confirmed, match_score
from app.services.verification.scoring import combine_trust, trust_level


@pytest.mark.no_db
def test_trust_level_boundaries() -> None:
    assert trust_level(0.85) == "high"
    assert trust_level(0.5) == "medium"
    assert trust_level(0.2) == "low"
    assert trust_level(0.19) == "none"


@pytest.mark.no_db
def test_trust_bonus_cannot_exceed_one() -> None:
    assert combine_trust(acoustid_score=0.9, musicbrainz_score=0.2, bonus=0.3) == 1.0


@pytest.mark.no_db
def test_source_match_confirms_close_duration() -> None:
    score = match_score(
        query="artist - title",
        candidate_title="title",
        candidate_artist="artist",
        duration_delta=1,
        isrc_match=False,
    )
    assert score >= 0.8
    assert is_confirmed(score, 1)


@pytest.mark.no_db
def test_source_match_rejects_duration_over_two_seconds() -> None:
    score = match_score(
        query="artist title",
        candidate_title="title",
        candidate_artist="artist",
        duration_delta=3,
        isrc_match=False,
    )
    assert not is_confirmed(score, 3)


@pytest.mark.no_db
def test_album_resolution_prefers_earliest_album() -> None:
    decision = decision_from_releases(
        [
            {
                "title": "Later",
                "date": "2010-01-01",
                "release-group": {"id": "later", "title": "Later", "primary-type": "Album"},
            },
            {
                "title": "Early",
                "date": "2001-05-01",
                "release-group": {"id": "early", "title": "Early", "primary-type": "Album"},
            },
            {
                "title": "Single",
                "date": "2000-01-01",
                "release-group": {"id": "single", "title": "Single", "primary-type": "Single"},
            },
        ],
        "Track",
        "recording-1",
    )
    assert decision.is_single is False
    assert decision.unresolved is False
    assert decision.title == "Early"
    assert decision.release_group_mbid == "early"
    assert decision.release_year == 2001


@pytest.mark.no_db
def test_album_resolution_single_only_when_every_release_is_single() -> None:
    decision = decision_from_releases(
        [
            {
                "title": "Single A",
                "date": "2004",
                "release-group": {"id": "s1", "primary-type": "Single"},
            }
        ],
        "Track Name",
    )
    assert decision.is_single is True
    assert decision.title == "Track Name"


@pytest.mark.no_db
def test_album_resolution_unresolved_is_not_a_single() -> None:
    decision = decision_from_releases(
        [{"title": "Compilation", "release-group": {"id": "c1", "primary-type": "Other"}}],
        "Track Name",
    )
    assert decision == unresolved_album("Track Name", None)
    assert decision.is_single is False
    assert decision.unresolved is True


@pytest.mark.no_db
def test_ep_counts_as_album() -> None:
    decision = decision_from_releases(
        [
            {
                "date": "1999",
                "release-group": {"id": "ep1", "title": "EP Title", "primary-type": "EP"},
            }
        ],
        "Track",
    )
    assert decision.is_single is False
    assert decision.title == "EP Title"


@pytest.mark.no_db
def test_identical_fingerprints_match() -> None:
    raw = [1, 2, 3, 4, 5]
    assert fingerprint_similarity(raw, raw) == 1.0


@pytest.mark.no_db
def test_album_resolution_model_roundtrip() -> None:
    raw = AlbumResolution(title="Container", unresolved=True, is_single=False)
    assert raw.is_single is False
