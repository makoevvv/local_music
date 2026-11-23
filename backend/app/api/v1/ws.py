from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.core.config import settings
from app.core.security import decode_access_token

router = APIRouter()


@router.websocket("/ws/tracks")
async def track_events(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    try:
        user_uuid = decode_access_token(token)
        user_id = str(user_uuid)
    except Exception:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    redis: Redis[str] = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    channel = f"track_events:{user_id}"
    await pubsub.subscribe(channel)

    async def reader() -> None:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                data = message.get("data")
                if isinstance(data, str):
                    await websocket.send_text(data)
            await asyncio.sleep(0.05)

    try:
        await reader()
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await redis.close()
