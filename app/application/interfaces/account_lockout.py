from abc import ABC, abstractmethod


class AccountLockout(ABC):
    @abstractmethod
    async def is_locked(self, key: str) -> bool: ...

    @abstractmethod
    async def record_failure(self, key: str) -> None: ...

    @abstractmethod
    async def clear(self, key: str) -> None: ...
