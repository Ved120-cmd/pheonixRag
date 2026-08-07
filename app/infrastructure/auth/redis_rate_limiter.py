from app.application.interfaces.rate_limiter import RateLimiter
from app.config.settings import get_settings
from app.infrastructure.cache.redis_client import get_redis_client

settings = get_settings()


class RedisRateLimiter(RateLimiter):
    def _key(self, identifier: str) -> str:
        return f"auth:rate:{identifier}"

    async def allow(self, key: str) -> bool:
        try:
            client = get_redis_client()
            count = await client.get(self._key(key))
            if count is None:
                return True
            return int(count) < settings.login_rate_limit_attempts
        except Exception:
            return True

    async def record_failure(self, key: str) -> None:
        try:
            client = get_redis_client()
            redis_key = self._key(key)
            pipe = client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, settings.login_rate_limit_window_seconds)
            await pipe.execute()
        except Exception:
            return

    async def clear(self, key: str) -> None:
        try:
            client = get_redis_client()
            await client.delete(self._key(key))
        except Exception:
            return
