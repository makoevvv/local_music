from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.selectable import Select

from app.models.catalog import Artist


def _normalized_name(name: str) -> str:
    collapsed = " ".join(name.split())
    return collapsed or "Unknown Artist"


def _clean_mbid(mbid: str | None) -> str | None:
    if mbid is None:
        return None
    cleaned = mbid.strip()
    return cleaned or None


def _remember_mbid(artist: Artist, mbid: str | None) -> Artist:
    if mbid and not artist.mbid:
        artist.mbid = mbid
    return artist


def _name_key() -> ColumnElement[str]:
    return func.lower(func.regexp_replace(Artist.name, r"\s+", " ", "g"))


def _by_mbid_stmt(mbid: str) -> Select[tuple[Artist]]:
    return select(Artist).where(Artist.mbid == mbid)


def _by_name_stmt(name: str, *, mbid: str | None) -> Select[tuple[Artist]]:
    key = _normalized_name(name).lower()
    stmt = select(Artist).where(_name_key() == key)
    if mbid:
        stmt = stmt.where(or_(Artist.mbid.is_(None), Artist.mbid == mbid))
    return stmt.order_by(Artist.created_at.asc()).limit(1)


def _new_artist(name: str, mbid: str | None, artist_id: uuid.UUID | None) -> Artist:
    display = _normalized_name(name)
    artist = Artist(name=display, sort_name=display, mbid=mbid)
    if artist_id is not None:
        artist.id = artist_id
    return artist


async def get_or_create_artist(
    session: AsyncSession,
    name: str,
    *,
    mbid: str | None = None,
    artist_id: uuid.UUID | None = None,
) -> Artist:
    """Reuse an artist by MusicBrainz id, then by name. Create one only when neither matches."""
    clean_mbid = _clean_mbid(mbid)
    if artist_id is not None:
        found = await session.get(Artist, artist_id)
        if found is not None:
            return _remember_mbid(found, clean_mbid)
    if clean_mbid:
        by_mbid = await session.scalar(_by_mbid_stmt(clean_mbid))
        if by_mbid is not None:
            return by_mbid
    by_name = await session.scalar(_by_name_stmt(name, mbid=clean_mbid))
    if by_name is not None:
        return _remember_mbid(by_name, clean_mbid)
    artist = _new_artist(name, clean_mbid, artist_id)
    session.add(artist)
    await session.flush()
    return artist


def get_or_create_artist_sync(
    session: Session,
    name: str,
    *,
    mbid: str | None = None,
    artist_id: uuid.UUID | None = None,
) -> Artist:
    clean_mbid = _clean_mbid(mbid)
    if artist_id is not None:
        found = session.get(Artist, artist_id)
        if found is not None:
            return _remember_mbid(found, clean_mbid)
    if clean_mbid:
        by_mbid = session.scalar(_by_mbid_stmt(clean_mbid))
        if by_mbid is not None:
            return by_mbid
    by_name = session.scalar(_by_name_stmt(name, mbid=clean_mbid))
    if by_name is not None:
        return _remember_mbid(by_name, clean_mbid)
    artist = _new_artist(name, clean_mbid, artist_id)
    session.add(artist)
    session.flush()
    return artist
