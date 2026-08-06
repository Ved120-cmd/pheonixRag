from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    @abstractmethod
    async def hash(self, password: str) -> str: ...

    @abstractmethod
    async def verify(self, password: str, hashed: str) -> bool: ...

    @abstractmethod
    async def needs_rehash(self, hashed: str) -> bool: ...
