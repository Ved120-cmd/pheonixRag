from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.admin_service import AdminService
from app.application.services.auth_service import AuthService
from app.application.services.user_service import UserService
from app.infrastructure.auth.in_memory_account_lockout import InMemoryAccountLockout
from app.infrastructure.auth.in_memory_rate_limiter import InMemoryRateLimiter
from app.infrastructure.auth.redis_account_lockout import RedisAccountLockout
from app.infrastructure.auth.redis_rate_limiter import RedisRateLimiter
from app.infrastructure.database.repositories.email_verification_repository import (
    SQLAlchemyEmailVerificationRepository,
)
from app.infrastructure.database.repositories.password_reset_repository import (
    SQLAlchemyPasswordResetRepository,
)
from app.infrastructure.database.repositories.refresh_token_repository import (
    SQLAlchemyRefreshTokenRepository,
)
from app.infrastructure.database.repositories.role_repository import SQLAlchemyRoleRepository
from app.infrastructure.database.repositories.user_repository import SQLAlchemyUserRepository
from app.infrastructure.database.session import get_db_session
from app.infrastructure.email.mock_email_service import MockEmailService
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.security.jwt_token_service import JWTTokenService
from app.application.services.document_service import DocumentService
from app.infrastructure.database.repositories.document_repository import (
    SQLAlchemyDocumentRepository,
)
from app.infrastructure.storage.document_store import DocumentStore

_password_hasher = Argon2PasswordHasher()
_token_service = JWTTokenService()
_email_service = MockEmailService()


def _get_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    try:
        return RedisRateLimiter()
    except Exception:
        return InMemoryRateLimiter()


def _get_account_lockout() -> InMemoryAccountLockout | RedisAccountLockout:
    try:
        return RedisAccountLockout()
    except Exception:
        return InMemoryAccountLockout()


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AuthService, None]:
    yield AuthService(
        user_repo=SQLAlchemyUserRepository(session),
        role_repo=SQLAlchemyRoleRepository(session),
        refresh_token_repo=SQLAlchemyRefreshTokenRepository(session),
        password_reset_repo=SQLAlchemyPasswordResetRepository(session),
        email_verification_repo=SQLAlchemyEmailVerificationRepository(session),
        password_hasher=_password_hasher,
        token_service=_token_service,
        email_service=_email_service,
        rate_limiter=_get_rate_limiter(),
        account_lockout=_get_account_lockout(),
    )


async def get_user_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[UserService, None]:
    yield UserService(
        user_repo=SQLAlchemyUserRepository(session),
        refresh_token_repo=SQLAlchemyRefreshTokenRepository(session),
        password_hasher=_password_hasher,
    )


async def get_admin_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AdminService, None]:
    yield AdminService(
        user_repo=SQLAlchemyUserRepository(session),
        role_repo=SQLAlchemyRoleRepository(session),
    )


async def get_document_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[DocumentService, None]:
    yield DocumentService(
        repo=SQLAlchemyDocumentRepository(session),
        store=DocumentStore(),
    )
