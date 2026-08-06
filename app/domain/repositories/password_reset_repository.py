from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.token import PasswordResetRecord


class PasswordResetRepository(ABC):
    @abstractmethod
    async def create(self, user_id: UUID, token: str) -> PasswordResetRecord: ...

    @abstractmethod
    async def get_valid(self, token: str) -> PasswordResetRecord | None: ...

    @abstractmethod
    async def mark_used(self, token: str) -> None: ...
