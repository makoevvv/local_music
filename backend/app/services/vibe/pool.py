from __future__ import annotations

from dataclasses import dataclass

from app.services.vibe.mood_profiles import MoodProfile
from app.services.vibe.scorer import passes_mood


@dataclass(frozen=True)
class Candidate:
    track_id: str
    bpm: float | None
    energy: float | None
    valence: float | None
    genre_names: tuple[str, ...]
    genre_ids: tuple[str, ...]
    artist_ids: tuple[str, ...]
    language_codes: tuple[str, ...]
    explicit: bool
    has_lyrics: bool
    play_count: int
    user_plays: int
    recently_played: bool


def select_candidates(
    candidates: list[Candidate],
    *,
    profile: MoodProfile,
    genres: list[str],
    languages: list[str],
    explicit_allowed: bool,
    no_lyrics: bool,
    excluded: set[str],
) -> list[Candidate]:
    wanted_genres = {item.lower() for item in genres}
    wanted_languages = set(languages)
    selected: list[Candidate] = []
    for candidate in candidates:
        if candidate.track_id in excluded:
            continue
        if not explicit_allowed and candidate.explicit:
            continue
        if no_lyrics and candidate.has_lyrics:
            continue
        if wanted_genres and not any(name in wanted_genres for name in candidate.genre_names):
            continue
        if wanted_languages and not any(code in wanted_languages for code in candidate.language_codes):
            continue
        if not passes_mood(
            bpm=candidate.bpm,
            energy=candidate.energy,
            valence=candidate.valence,
            genre_names=candidate.genre_names,
            profile=profile,
        ):
            continue
        selected.append(candidate)
    return selected
