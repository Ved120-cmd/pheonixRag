from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Permission:
    id: UUID
    name: str
    description: str | None
