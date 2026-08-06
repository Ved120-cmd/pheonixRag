from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.domain.entities.token import RefreshTokenRecord
from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.database.mappers import refresh_token_to_entity
from app.infrastructure.database.models.refresh_token import RefreshTokenModel
from app.infrastructure.security.token_hash import hash_token

settings = get_settings()


class SQLAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store(self, user_id: UUID, token: str, expires_at: datetime) -> RefreshTokenRecord:
        model = RefreshTokenModel(
            id=uuid4(),
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return refresh_token_to_entity(model)

    async def get_by_token(self, token: str) -> RefreshTokenRecord | None:
        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == hash_token(token))
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        expires_at = model.expires_at if model.expires_at.tzinfo is not None else model.expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            return None

        return refresh_token_to_entity(model)

    async def revoke(self, token: str) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == hash_token(token))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.commit()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.commit()
