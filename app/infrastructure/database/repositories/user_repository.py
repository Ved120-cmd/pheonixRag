from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.database.mappers import user_to_entity, user_to_model
from app.infrastructure.database.models.user import UserModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _active_only() -> bool:
        return UserModel.deleted_at.is_(None)

    async def create(self, user: User) -> User:
        model = user_to_model(user)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return user_to_entity(model)

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id, self._active_only())
        )
        model = result.scalar_one_or_none()
        return user_to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email, self._active_only())
        )
        model = result.scalar_one_or_none()
        return user_to_entity(model) if model else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.username == username, self._active_only())
        )
        model = result.scalar_one_or_none()
        return user_to_entity(model) if model else None

    async def update(self, user: User) -> User:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user.id)
        )
        model = result.scalar_one()
        model.email = user.email
        model.username = user.username
        model.full_name = user.full_name
        model.hashed_password = user.hashed_password
        model.avatar_url = user.avatar_url
        model.role_id = user.role_id
        model.is_active = user.is_active
        model.is_verified = user.is_verified
        model.deleted_at = user.deleted_at
        model.last_login = user.last_login
        model.updated_at = user.updated_at
        await self._session.commit()
        await self._session.refresh(model)
        return user_to_entity(model)

    async def delete(self, user_id: UUID) -> None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id, self._active_only())
        )
        model = result.scalar_one_or_none()
        if model is None:
            return
        now = datetime.now(UTC)
        model.is_active = False
        model.deleted_at = now
        model.updated_at = now
        await self._session.commit()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        result = await self._session.execute(
            select(UserModel)
            .where(self._active_only())
            .offset(skip)
            .limit(limit)
            .order_by(UserModel.created_at.desc())
        )
        return [user_to_entity(m) for m in result.scalars().all()]

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(UserModel).where(self._active_only())
        )
        return result.scalar_one() or 0

    async def email_exists(self, email: str) -> bool:
        result = await self._session.execute(
            select(func.count()).select_from(UserModel).where(UserModel.email == email)
        )
        return (result.scalar_one() or 0) > 0

    async def username_exists(self, username: str) -> bool:
        result = await self._session.execute(
            select(func.count()).select_from(UserModel).where(UserModel.username == username)
        )
        return (result.scalar_one() or 0) > 0
