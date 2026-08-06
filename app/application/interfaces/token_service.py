from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TokenPayload:
    user_id: UUID
    role_name: str | None = None


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class TokenService(ABC):
    @abstractmethod
    def create_token_pair(self, user_id: UUID, role_name: str) -> TokenPair: ...

    @abstractmethod
    def decode_access_token(self, token: str) -> TokenPayload: ...

    @abstractmethod
    def decode_refresh_token(self, token: str) -> TokenPayload: ...
