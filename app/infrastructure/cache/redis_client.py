"""Redis client wrapper."""

from functools import lru_cache

import redis.asyncio as redis

from app.config.settings import get_settings

settings = get_settings()


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def check_redis_health() -> bool:
    """Lightweight connectivity check used by the /health endpoint."""
    try:
        client = get_redis_client()
        return bool(await client.ping())
    except Exception:
        return False
