from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db_session
from app.main import app


@pytest.fixture
async def engine(request: pytest.FixtureRequest):
    if request.node.get_closest_marker("no_db"):
        yield None
        return
    test_engine = create_async_engine(settings.database_url)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables(engine, request: pytest.FixtureRequest) -> AsyncIterator[None]:
    if request.node.get_closest_marker("no_db"):
        yield
        return
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE likes, plays, playlist_tracks, playlists, track_languages, "
                "track_genres, track_artists, tracks, albums, artists, "
                "refresh_tokens, invites, audit_log, users RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
