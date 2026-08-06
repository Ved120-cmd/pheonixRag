from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.token import RefreshTokenRecord


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def store(self, user_id: UUID, token: str, expires_at: datetime) -> RefreshTokenRecord: ...

    @abstractmethod
    async def get_by_token(self, token: str) -> RefreshTokenRecord | None: ...

    @abstractmethod
    async def revoke(self, token: str) -> None: ...

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UUID) -> None: ...
