from __future__ import annotations

import pytest

from app.services.vibe.mood_profiles import mood_profile
from app.services.vibe.pool import Candidate, select_candidates
from app.services.vibe.scorer import boltzmann_sample, passes_mood, score_parts

pytestmark = pytest.mark.no_db


def _candidate(**overrides: object) -> Candidate:
    payload: dict[str, object] = {
        "track_id": "track",
        "bpm": 100.0,
        "energy": 0.5,
        "valence": 0.5,
        "genre_names": (),
        "genre_ids": (),
        "artist_ids": (),
        "language_codes": (),
        "explicit": False,
        "has_lyrics": True,
        "play_count": 0,
        "user_plays": 0,
        "recently_played": False,
    }
    payload.update(overrides)
    return Candidate(**payload)  # type: ignore[arg-type]


def test_calm_mood_rejects_fast_loud_tracks() -> None:
    calm = mood_profile("calm")
    assert passes_mood(bpm=72, energy=0.2, valence=0.5, genre_names=[], profile=calm)
    assert not passes_mood(bpm=160, energy=0.9, valence=0.8, genre_names=[], profile=calm)


def test_missing_features_follow_genre_hint() -> None:
    calm = mood_profile("calm")
    assert passes_mood(bpm=None, energy=None, valence=None, genre_names=["jazz"], profile=calm)
    assert not passes_mood(bpm=None, energy=None, valence=None, genre_names=["metal"], profile=calm)


def test_filters_narrow_the_pool() -> None:
    calm = _candidate(track_id="calm", bpm=70, energy=0.2, valence=0.5, genre_names=("jazz",))
    party = _candidate(track_id="party", bpm=130, energy=0.9, valence=0.8, genre_names=("edm",))
    explicit = _candidate(
        track_id="explicit",
        bpm=70,
        energy=0.2,
        valence=0.5,
        explicit=True,
    )
    selected = select_candidates(
        [calm, party, explicit],
        profile=mood_profile("calm"),
        genres=["jazz"],
        languages=[],
        explicit_allowed=False,
        no_lyrics=False,
        excluded=set(),
    )
    assert [item.track_id for item in selected] == ["calm"]


def test_boltzmann_sample_is_stable_for_a_fixed_seed() -> None:
    scored = [("a", 1.2), ("b", 0.1), ("c", 0.4), ("d", -0.2)]
    first = boltzmann_sample(scored, 3, seed=7, temperature=0.6)
    second = boltzmann_sample(scored, 3, seed=7, temperature=0.6)
    assert first == second
    assert len(first) == 3
    assert len(set(first)) == 3


def test_score_penalises_recent_and_dislike() -> None:
    base = score_parts(
        mood_match=1, affinity=0, novelty=0.6, popularity=0.2, recent=0, dislike=0
    )
    penalised = score_parts(
        mood_match=1, affinity=0, novelty=0.6, popularity=0.2, recent=1, dislike=1
    )
    assert penalised < base
