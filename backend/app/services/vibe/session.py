from __future__ import annotations

import json
from typing import TypedDict, cast

from app.core.sync_redis import get_sync_redis

_TTL_SECONDS = 60 * 60 * 6


class VibeState(TypedDict):
    user_id: str
    mood: str
    genres: list[str]
    languages: list[str]
    mode: str
    explicit_allowed: bool
    no_lyrics: bool
    seed: int
    batch: int
    excluded: list[str]


def _key(session_id: str) -> str:
    return f"vibe:{session_id}:state"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def save_session(session_id: str, payload: VibeState) -> None:
    get_sync_redis().setex(_key(session_id), _TTL_SECONDS, json.dumps(payload))


def load_session(session_id: str) -> VibeState | None:
    raw = get_sync_redis().get(_key(session_id))
    if not isinstance(raw, str):
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None
    payload = cast(dict[str, object], data)
    user_id = payload.get("user_id")
    if not isinstance(user_id, str):
        return None
    seed = payload.get("seed")
    batch = payload.get("batch")
    return VibeState(
        user_id=user_id,
        mood=str(payload.get("mood") or "neutral"),
        genres=_string_list(payload.get("genres")),
        languages=_string_list(payload.get("languages")),
        mode=str(payload.get("mode") or "mixed"),
        explicit_allowed=bool(payload.get("explicit_allowed", True)),
        no_lyrics=bool(payload.get("no_lyrics", False)),
        seed=int(seed) if isinstance(seed, int | float) else 1,
        batch=int(batch) if isinstance(batch, int | float) else 0,
        excluded=_string_list(payload.get("excluded")),
    )
