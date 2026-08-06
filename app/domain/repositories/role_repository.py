from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.role import Role


class RoleRepository(ABC):
    @abstractmethod
    async def get_by_id(self, role_id: UUID) -> Role | None: ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Role | None: ...

    @abstractmethod
    async def list_all(self) -> list[Role]: ...
