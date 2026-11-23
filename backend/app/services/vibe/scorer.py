from __future__ import annotations

import math
import random

from app.services.vibe.mood_profiles import MoodProfile

W_MOOD = 0.35
W_AFFINITY = 0.25
W_NOVELTY = 0.15
W_POPULARITY = 0.10
W_RECENT = 0.15
W_DISLIKE = 0.30


def score_parts(
    *,
    mood_match: float,
    affinity: float,
    novelty: float,
    popularity: float,
    recent: float,
    dislike: float,
) -> float:
    return (
        W_MOOD * mood_match
        + W_AFFINITY * affinity
        + W_NOVELTY * novelty
        + W_POPULARITY * popularity
        - W_RECENT * recent
        - W_DISLIKE * dislike
    )


def popularity(play_count: int) -> float:
    return min(1.0, math.log(play_count + 1) / math.log(100))


def squash_affinity(value: float) -> float:
    return math.tanh(value / 5)


def novelty_for(mode: str, user_plays: int) -> float:
    if mode == "discover":
        return 1.0 if user_plays == 0 else 0.2
    if mode == "familiar":
        return 1.0 if user_plays else 0.3
    return 0.6


def _in_bounds(value: float, low: float | None, high: float | None) -> bool:
    if low is not None and value < low:
        return False
    return not (high is not None and value > high)


def resolved_features(
    *,
    bpm: float | None,
    energy: float | None,
    valence: float | None,
    genre_names: tuple[str, ...] | list[str],
    profile: MoodProfile,
) -> tuple[float, float, float]:
    hinted = any(name in profile.genres for name in genre_names)
    bpm_value = profile.default_bpm if bpm is None and hinted else (100.0 if bpm is None else bpm)
    energy_value = (
        profile.default_energy if energy is None and hinted else (0.5 if energy is None else energy)
    )
    valence_value = (
        profile.default_valence
        if valence is None and hinted
        else (0.5 if valence is None else valence)
    )
    return bpm_value, energy_value, valence_value


def passes_mood(
    *,
    bpm: float | None,
    energy: float | None,
    valence: float | None,
    genre_names: tuple[str, ...] | list[str],
    profile: MoodProfile,
) -> bool:
    resolved_bpm, resolved_energy, resolved_valence = resolved_features(
        bpm=bpm,
        energy=energy,
        valence=valence,
        genre_names=genre_names,
        profile=profile,
    )
    bpm_ok = profile.bpm is None or _in_bounds(resolved_bpm, profile.bpm[0], profile.bpm[1])
    return (
        bpm_ok
        and _in_bounds(resolved_energy, profile.energy_min, profile.energy_max)
        and _in_bounds(resolved_valence, profile.valence_min, profile.valence_max)
    )


def mood_match(
    *,
    bpm: float | None,
    energy: float | None,
    valence: float | None,
    genre_names: tuple[str, ...] | list[str],
    genre_ids: tuple[str, ...] | list[str],
    profile: MoodProfile,
    preferred_genre_ids: set[str],
) -> float:
    if not passes_mood(
        bpm=bpm, energy=energy, valence=valence, genre_names=genre_names, profile=profile
    ):
        return 0.0
    if profile.genres and any(name in profile.genres for name in genre_names):
        return 1.0
    if preferred_genre_ids and any(genre_id in preferred_genre_ids for genre_id in genre_ids):
        return 1.0
    return 0.7


def boltzmann_sample(
    scored: list[tuple[str, float]],
    k: int,
    seed: int,
    temperature: float,
) -> list[str]:
    rng = random.Random(seed)
    pool = list(scored)
    chosen: list[str] = []
    temp = max(temperature, 0.05)
    for _ in range(min(k, len(pool))):
        weights = [math.exp(score / temp) for _, score in pool]
        total = sum(weights) or 1.0
        cursor = rng.random() * total
        acc = 0.0
        index = len(pool) - 1
        for position, weight in enumerate(weights):
            acc += weight
            if acc >= cursor:
                index = position
                break
        track_id, _score = pool.pop(index)
        chosen.append(track_id)
    return chosen
