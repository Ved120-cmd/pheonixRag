from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.domain.entities.token import PasswordResetRecord
from app.domain.repositories.password_reset_repository import PasswordResetRepository
from app.infrastructure.database.mappers import password_reset_to_entity
from app.infrastructure.database.models.password_reset_token import PasswordResetTokenModel
from app.infrastructure.security.token_hash import hash_token

settings = get_settings()


class SQLAlchemyPasswordResetRepository(PasswordResetRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: UUID, token: str) -> PasswordResetRecord:
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.password_reset_token_expire_minutes)
        model = PasswordResetTokenModel(
            id=uuid4(),
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return password_reset_to_entity(model)

    async def get_valid(self, token: str) -> PasswordResetRecord | None:
        result = await self._session.execute(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.token_hash == hash_token(token)
            )
        )
        model = result.scalar_one_or_none()
        if model is None or model.used_at is not None:
            return None
        expires_at = model.expires_at if model.expires_at.tzinfo is not None else model.expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            return None

        return password_reset_to_entity(model)

    async def mark_used(self, token: str) -> None:
        await self._session.execute(
            update(PasswordResetTokenModel)
            .where(PasswordResetTokenModel.token_hash == hash_token(token))
            .values(used_at=datetime.now(UTC))
        )
        await self._session.commit()
