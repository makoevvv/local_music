from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis[str] | None = None


async def init_redis() -> Redis[str]:
    global _redis
    client: Redis[str] = Redis.from_url(settings.redis_url, decode_responses=True)
    await client.ping()
    _redis = client
    return client


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


def get_redis() -> Redis[str]:
    if _redis is None:
        msg = "Redis client is not initialized"
        raise RuntimeError(msg)
    return _redis
