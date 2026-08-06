"""In-memory account lockout for tests and environments without Redis."""

from app.application.interfaces.account_lockout import AccountLockout
from app.config.settings import get_settings

settings = get_settings()


class InMemoryAccountLockout(AccountLockout):
    def __init__(self) -> None:
        self._failures: dict[str, int] = {}
        self._locked: set[str] = set()

    async def is_locked(self, key: str) -> bool:
        return key in self._locked

    async def record_failure(self, key: str) -> None:
        self._failures[key] = self._failures.get(key, 0) + 1
        if self._failures[key] >= settings.account_lockout_threshold:
            self._locked.add(key)

    async def clear(self, key: str) -> None:
        self._failures.pop(key, None)
        self._locked.discard(key)
