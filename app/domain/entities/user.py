from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.role import Role


@dataclass(frozen=True, slots=True)
class User:
    """Pure domain user — no ORM, no Pydantic.

    OAuth extensibility: a future auth_identities table will link external
    providers (google, github) to this entity via user_id.
    """

    id: UUID
    email: str
    username: str
    full_name: str | None
    hashed_password: str
    avatar_url: str | None
    role_id: UUID
    role: Role | None
    is_active: bool
    is_verified: bool
    deleted_at: datetime | None
    last_login: datetime | None
    created_at: datetime
    updated_at: datetime

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def has_permission(self, permission_name: str) -> bool:
        if self.role is None:
            return False
        return any(p.name == permission_name for p in self.role.permissions)
