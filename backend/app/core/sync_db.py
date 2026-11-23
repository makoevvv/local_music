from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — register all ORM mappers for sync worker sessions
from app.core.config import settings


def _sync_database_url() -> str:
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url


_engine = create_engine(_sync_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


@contextmanager
def sync_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
