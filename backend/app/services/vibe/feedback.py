from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sync_redis import get_sync_redis
from app.models.vibe import UserAffinity

AFFINITY_WEIGHTS: dict[str, float] = {
    "like": 3.0,
    "dislike": -5.0,
    "skip": -1.0,
    "played": 1.0,
}
_AFFINITY_TTL = 60 * 60 * 24 * 30


def affinity_key(user_id: uuid.UUID, kind: str) -> str:
    return f"vibe:affinity:{user_id}:{kind}"


def read_affinity(user_id: uuid.UUID, kind: str, target_id: str) -> float | None:
    raw = get_sync_redis().hget(affinity_key(user_id, kind), target_id)
    if raw is None:
        return None
    return float(raw)


def read_affinity_map(user_id: uuid.UUID, kind: str) -> dict[str, float]:
    raw = get_sync_redis().hgetall(affinity_key(user_id, kind))
    return {str(key): float(value) for key, value in raw.items()}


def add_affinity(user_id: uuid.UUID, kind: str, target_id: str, delta: float) -> float:
    key = affinity_key(user_id, kind)
    updated = float(get_sync_redis().hincrbyfloat(key, target_id, delta))
    get_sync_redis().expire(key, _AFFINITY_TTL)
    return updated


async def snapshot_affinity(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: str,
    target_id: str,
    score: float,
) -> None:
    row = await db.scalar(
        select(UserAffinity).where(
            UserAffinity.user_id == user_id,
            UserAffinity.target_kind == kind,
            UserAffinity.target_id == target_id,
        )
    )
    if row is None:
        db.add(
            UserAffinity(
                user_id=user_id,
                target_kind=kind,
                target_id=target_id,
                score=score,
            )
        )
        return
    row.score = score
    row.updated_at = datetime.now(UTC)


async def apply_feedback(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    artist_ids: list[str],
    genre_ids: list[str],
    action: str,
) -> None:
    delta = AFFINITY_WEIGHTS[action]
    for artist_id in artist_ids:
        score = add_affinity(user_id, "artist", artist_id, delta)
        await snapshot_affinity(db, user_id=user_id, kind="artist", target_id=artist_id, score=score)
    for genre_id in genre_ids:
        score = add_affinity(user_id, "genre", genre_id, delta)
        await snapshot_affinity(db, user_id=user_id, kind="genre", target_id=genre_id, score=score)
    await db.commit()
