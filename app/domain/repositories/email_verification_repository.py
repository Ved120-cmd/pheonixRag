from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.token import EmailVerificationRecord


class EmailVerificationRepository(ABC):
    @abstractmethod
    async def create(self, user_id: UUID, token: str) -> EmailVerificationRecord: ...

    @abstractmethod
    async def get_valid(self, token: str) -> EmailVerificationRecord | None: ...

    @abstractmethod
    async def mark_used(self, token: str) -> None: ...
