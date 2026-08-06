"""In-memory rate limiter for tests and environments without Redis."""

from app.application.interfaces.rate_limiter import RateLimiter
from app.config.settings import get_settings

settings = get_settings()


class InMemoryRateLimiter(RateLimiter):
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def allow(self, key: str) -> bool:
        return self._counts.get(key, 0) < settings.login_rate_limit_attempts

    async def record_failure(self, key: str) -> None:
        self._counts[key] = self._counts.get(key, 0) + 1

    async def clear(self, key: str) -> None:
        self._counts.pop(key, None)
