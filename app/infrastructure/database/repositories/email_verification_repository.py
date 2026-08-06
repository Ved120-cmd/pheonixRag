from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.domain.entities.token import EmailVerificationRecord
from app.domain.repositories.email_verification_repository import EmailVerificationRepository
from app.infrastructure.database.mappers import email_verification_to_entity
from app.infrastructure.database.models.email_verification_token import EmailVerificationTokenModel
from app.infrastructure.security.token_hash import hash_token

settings = get_settings()


class SQLAlchemyEmailVerificationRepository(EmailVerificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: UUID, token: str) -> EmailVerificationRecord:
        expires_at = datetime.now(UTC) + timedelta(hours=settings.email_verification_token_expire_hours)
        model = EmailVerificationTokenModel(
            id=uuid4(),
            user_id=user_id,
            token_hash=hash_token(token),
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return email_verification_to_entity(model)

    async def get_valid(self, token: str) -> EmailVerificationRecord | None:
        result = await self._session.execute(
            select(EmailVerificationTokenModel).where(
                EmailVerificationTokenModel.token_hash == hash_token(token)
            )
        )
        model = result.scalar_one_or_none()
        if model is None or model.used_at is not None:
            return None
        expires_at = model.expires_at if model.expires_at.tzinfo is not None else model.expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            return None

        return email_verification_to_entity(model)

    async def mark_used(self, token: str) -> None:
        await self._session.execute(
            update(EmailVerificationTokenModel)
            .where(EmailVerificationTokenModel.token_hash == hash_token(token))
            .values(used_at=datetime.now(UTC))
        )
        await self._session.commit()
