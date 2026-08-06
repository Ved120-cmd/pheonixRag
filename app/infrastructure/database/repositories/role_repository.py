from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.role import Role
from app.domain.repositories.role_repository import RoleRepository
from app.infrastructure.database.mappers import role_to_entity
from app.infrastructure.database.models.role import RoleModel


class SQLAlchemyRoleRepository(RoleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, role_id: UUID) -> Role | None:
        result = await self._session.execute(select(RoleModel).where(RoleModel.id == role_id))
        model = result.scalar_one_or_none()
        return role_to_entity(model) if model else None

    async def get_by_name(self, name: str) -> Role | None:
        result = await self._session.execute(select(RoleModel).where(RoleModel.name == name))
        model = result.scalar_one_or_none()
        return role_to_entity(model) if model else None

    async def list_all(self) -> list[Role]:
        result = await self._session.execute(select(RoleModel).order_by(RoleModel.name))
        return [role_to_entity(m) for m in result.scalars().all()]
