from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.api.health import router as health_router
from app.core.database import engine
from app.core.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    await init_redis()
    yield
    await engine.dispose()
    await close_redis()


app = FastAPI(title="Local Music API", lifespan=lifespan)
app.include_router(health_router)
