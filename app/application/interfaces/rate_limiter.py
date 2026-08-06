from abc import ABC, abstractmethod


class RateLimiter(ABC):
    @abstractmethod
    async def allow(self, key: str) -> bool: ...

    @abstractmethod
    async def record_failure(self, key: str) -> None: ...

    @abstractmethod
    async def clear(self, key: str) -> None: ...
