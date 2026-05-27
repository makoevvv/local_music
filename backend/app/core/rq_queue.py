from __future__ import annotations

from redis import Redis
from rq import Queue

from app.core.config import settings


def get_queue() -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue(settings.rq_queue_name, connection=connection)
