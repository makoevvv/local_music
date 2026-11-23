from __future__ import annotations

import re

# docs/14-user-upload.md §3. Duration term is 0 when |Δ| > 5s.
# Title/artist is a token-set overlap. ISRC adds a fixed bonus, capped at 1.
DURATION_ZERO_SECONDS = 5.0
WEIGHT_DURATION = 0.45
WEIGHT_TEXT = 0.55
ISRC_BONUS = 0.3
CONFIRM_SCORE = 0.8
CONFIRM_DURATION_SECONDS = 2

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN.findall(value.lower()))


def token_set_ratio(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def duration_component(delta_seconds: float | None) -> float:
    if delta_seconds is None:
        return 0.0
    absolute = abs(delta_seconds)
    if absolute > DURATION_ZERO_SECONDS:
        return 0.0
    return 1.0 - (absolute / DURATION_ZERO_SECONDS)


def match_score(
    *,
    query: str,
    candidate_title: str,
    candidate_artist: str,
    duration_delta: float | None,
    isrc_match: bool,
) -> float:
    text = token_set_ratio(query, f"{candidate_artist} {candidate_title}")
    score = (WEIGHT_DURATION * duration_component(duration_delta)) + (WEIGHT_TEXT * text)
    if isrc_match:
        score += ISRC_BONUS
    return min(1.0, score)


def is_confirmed(score: float, duration_delta: float | None) -> bool:
    if duration_delta is None or abs(duration_delta) > CONFIRM_DURATION_SECONDS:
        return False
    return score >= CONFIRM_SCORE
