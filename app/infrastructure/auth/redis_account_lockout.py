from app.application.interfaces.account_lockout import AccountLockout
from app.config.settings import get_settings
from app.infrastructure.cache.redis_client import get_redis_client

settings = get_settings()


class RedisAccountLockout(AccountLockout):
    def _fail_key(self, identifier: str) -> str:
        return f"auth:lockout:failures:{identifier}"

    def _lock_key(self, identifier: str) -> str:
        return f"auth:lockout:locked:{identifier}"

    async def is_locked(self, key: str) -> bool:
        client = get_redis_client()
        return bool(await client.exists(self._lock_key(key)))

    async def record_failure(self, key: str) -> None:
        client = get_redis_client()
        fail_key = self._fail_key(key)
        failures = await client.incr(fail_key)
        await client.expire(fail_key, settings.account_lockout_duration_seconds)

        if failures >= settings.account_lockout_threshold:
            await client.setex(
                self._lock_key(key),
                settings.account_lockout_duration_seconds,
                "1",
            )

    async def clear(self, key: str) -> None:
        client = get_redis_client()
        await client.delete(self._fail_key(key), self._lock_key(key))
