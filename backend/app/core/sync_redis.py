from __future__ import annotations

import json
from typing import Any

import redis

from app.core.config import settings

_sync_redis: redis.Redis[str] | None = None


def get_sync_redis() -> redis.Redis[str]:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_redis


def publish_track_event(user_id: str, payload: dict[str, Any]) -> None:
    channel = f"track_events:{user_id}"
    get_sync_redis().publish(channel, json.dumps(payload))


def search_cache_key(query_hash: str) -> str:
    return f"search:v1:{query_hash}"


def get_search_cache(query_hash: str) -> list[str] | None:
    raw = get_sync_redis().get(search_cache_key(query_hash))
    if raw is None:
        return None
    data = json.loads(raw)
    if isinstance(data, list):
        return [str(item) for item in data]
    return None


def set_search_cache(query_hash: str, candidate_ids: list[str], ttl_seconds: int) -> None:
    get_sync_redis().setex(
        search_cache_key(query_hash),
        ttl_seconds,
        json.dumps(candidate_ids),
    )
