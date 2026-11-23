from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MoodProfile:
    bpm: tuple[float, float] | None
    energy_min: float | None
    energy_max: float | None
    valence_min: float | None
    valence_max: float | None
    genres: tuple[str, ...]
    default_bpm: float
    default_energy: float
    default_valence: float


MOODS: dict[str, MoodProfile] = {
    "calm": MoodProfile(
        (60, 90), None, 0.4, 0.3, 0.7, ("ambient", "jazz", "classical", "post-rock"), 75, 0.3, 0.5
    ),
    "energetic": MoodProfile(
        (120, 180), 0.65, None, 0.5, None, ("rock", "edm", "hip-hop"), 140, 0.75, 0.7
    ),
    "sad": MoodProfile(
        (60, 100), None, 0.5, None, 0.4, ("indie", "acoustic", "blues"), 80, 0.35, 0.25
    ),
    "happy": MoodProfile((100, 140), 0.5, 0.8, 0.65, None, ("pop", "funk"), 120, 0.65, 0.75),
    "focus": MoodProfile(
        (70, 110), 0.3, 0.55, 0.4, 0.6, ("lo-fi", "instrumental", "ambient"), 90, 0.4, 0.5
    ),
    "party": MoodProfile(
        (110, 140), 0.7, None, 0.55, None, ("edm", "hip-hop", "pop"), 125, 0.8, 0.7
    ),
    "neutral": MoodProfile(None, None, None, None, None, (), 100, 0.5, 0.5),
}


def mood_profile(mood: str) -> MoodProfile:
    return MOODS.get(mood, MOODS["neutral"])
