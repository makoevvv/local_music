from __future__ import annotations

from app.schemas.upload import TrustLevelName


def trust_level(score: float) -> TrustLevelName:
    if score >= 0.85:
        return "high"
    if score >= 0.5:
        return "medium"
    if score >= 0.2:
        return "low"
    return "none"


def heuristic_bonus(
    *,
    has_tags: bool,
    year: int | None,
    duration_seconds: int | None,
    bitrate: int | None,
    sample_rate: int | None,
) -> float:
    bonus = 0.0
    if has_tags:
        bonus += 0.08
    if year is not None and 1900 <= year <= 2100:
        bonus += 0.04
    duration_ok = duration_seconds is not None and 30 <= duration_seconds <= 20 * 60
    rate_ok = sample_rate is None or sample_rate in {22050, 32000, 44100, 48000, 88200, 96000}
    bitrate_ok = bitrate is None or 32_000 <= bitrate <= 2_000_000
    if duration_ok and rate_ok and bitrate_ok:
        bonus += 0.08
    return bonus


def combine_trust(*, acoustid_score: float, musicbrainz_score: float, bonus: float) -> float:
    base = max(0.0, acoustid_score, musicbrainz_score)
    return min(1.0, base + max(0.0, bonus))
