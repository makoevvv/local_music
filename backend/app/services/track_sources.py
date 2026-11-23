from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.catalog import TrackSource

# Tier → recovery_priority (lower = try first). See docs/06-music-sourcing.md.
TIER_PRIORITY = {1: 10, 2: 30, 3: 60, 4: 200}

KIND_PRIORITY = {
    "soundcloud": 10,
    "bandcamp": 10,
    "archive_org": 10,
    "fma": 10,
    "jamendo": 10,
    "youtube": 30,
    "direct_url": 30,
    "vimeo": 30,
    "user_upload": 60,
    "upload": 60,
    "unknown": 100,
}


def recovery_priority_for(*, tier: int | None = None, source_kind: str | None = None) -> int:
    if tier is not None and tier in TIER_PRIORITY:
        return TIER_PRIORITY[tier]
    kind = (source_kind or "unknown").lower()
    if kind.startswith("restricted:"):
        return 200
    return KIND_PRIORITY.get(kind, 100)


def normalize_source_kind(source_kind: str | None) -> str:
    if not source_kind:
        return "unknown"
    if source_kind == "upload":
        return "user_upload"
    return source_kind


def build_track_source(
    *,
    track_id: uuid.UUID,
    source_kind: str | None,
    source_url: str | None = None,
    source_id: str | None = None,
    added_by_user_id: uuid.UUID | None = None,
    tier: int | None = None,
    original_filename: str | None = None,
    original_tags: dict[str, Any] | None = None,
    last_status: str | None = None,
    recovery_priority: int | None = None,
) -> TrackSource:
    kind = normalize_source_kind(source_kind)
    priority = recovery_priority
    if priority is None:
        priority = recovery_priority_for(tier=tier, source_kind=kind)
    return TrackSource(
        track_id=track_id,
        source_kind=kind,
        source_url=source_url or None,
        source_id=source_id,
        original_filename=original_filename,
        original_tags=original_tags or {},
        added_by_user_id=added_by_user_id,
        recovery_priority=priority,
        last_status=last_status,
    )


async def add_track_source(session: AsyncSession, source: TrackSource) -> TrackSource:
    session.add(source)
    await session.flush()
    return source


def mark_sources_status_sync(
    session: Session,
    track_id: uuid.UUID,
    *,
    status: str,
    source_kind: str | None = None,
    source_id: str | None = None,
) -> None:
    stmt = select(TrackSource).where(TrackSource.track_id == track_id)
    if source_kind:
        stmt = stmt.where(TrackSource.source_kind == normalize_source_kind(source_kind))
    if source_id:
        stmt = stmt.where(TrackSource.source_id == source_id)
    now = datetime.now(UTC)
    for source in session.scalars(stmt).all():
        source.last_status = status
        source.last_checked_at = now
