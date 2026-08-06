from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.permission import Permission


@dataclass(frozen=True, slots=True)
class Role:
    id: UUID
    name: str
    description: str | None
    permissions: tuple[Permission, ...] = ()
