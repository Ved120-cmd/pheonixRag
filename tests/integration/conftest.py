from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies.services import get_auth_service, get_admin_service, get_user_service
from app.application.services.auth_service import AuthService
from app.application.services.admin_service import AdminService
from app.application.services.user_service import UserService
from app.domain.entities.user import User
from app.infrastructure.auth.in_memory_account_lockout import InMemoryAccountLockout
from app.infrastructure.auth.in_memory_rate_limiter import InMemoryRateLimiter
from app.infrastructure.database.base import Base
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
from app.main import app
from app.scripts.seed_iam import seed_iam

_password_hasher = Argon2PasswordHasher()
_token_service = JWTTokenService()
_email_service = MockEmailService()
_rate_limiter = InMemoryRateLimiter()
_account_lockout = InMemoryAccountLockout()


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    return async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def seeded_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        await seed_iam(session)
        yield session


def _build_auth_service(session: AsyncSession) -> AuthService:
    return AuthService(
        user_repo=SQLAlchemyUserRepository(session),
        role_repo=SQLAlchemyRoleRepository(session),
        refresh_token_repo=SQLAlchemyRefreshTokenRepository(session),
        password_reset_repo=SQLAlchemyPasswordResetRepository(session),
        email_verification_repo=SQLAlchemyEmailVerificationRepository(session),
        password_hasher=_password_hasher,
        token_service=_token_service,
        email_service=_email_service,
        rate_limiter=_rate_limiter,
        account_lockout=_account_lockout,
    )


def _build_user_service(session: AsyncSession) -> UserService:
    return UserService(
        user_repo=SQLAlchemyUserRepository(session),
        refresh_token_repo=SQLAlchemyRefreshTokenRepository(session),
        password_hasher=_password_hasher,
    )


def _build_admin_service(session: AsyncSession) -> AdminService:
    return AdminService(
        user_repo=SQLAlchemyUserRepository(session),
        role_repo=SQLAlchemyRoleRepository(session),
    )


@pytest.fixture
async def client(session_factory, seeded_session) -> AsyncGenerator[AsyncClient, None]:
    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            await seed_iam(session)
            yield session

    async def override_auth_service() -> AsyncGenerator[AuthService, None]:
        async with session_factory() as session:
            await seed_iam(session)
            yield _build_auth_service(session)

    async def override_user_service() -> AsyncGenerator[UserService, None]:
        async with session_factory() as session:
            yield _build_user_service(session)

    async def override_admin_service() -> AsyncGenerator[AdminService, None]:
        async with session_factory() as session:
            await seed_iam(session)
            yield _build_admin_service(session)

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_auth_service] = override_auth_service
    app.dependency_overrides[get_user_service] = override_user_service
    app.dependency_overrides[get_admin_service] = override_admin_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def strong_password() -> str:
    return "Str0ng!Pass"


@pytest.fixture
async def registered_user(client: AsyncClient, strong_password: str) -> dict:
    response = await client.post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "username": "testuser",
            "password": strong_password,
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
async def auth_tokens(client: AsyncClient, strong_password: str, registered_user: dict) -> dict:
    response = await client.post(
        "/auth/login",
        json={"identifier": "user@example.com", "password": strong_password},
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
async def admin_tokens(
    client: AsyncClient, session_factory, strong_password: str
) -> dict:
    async with session_factory() as session:
        await seed_iam(session)
        role_repo = SQLAlchemyRoleRepository(session)
        user_repo = SQLAlchemyUserRepository(session)
        admin_role = await role_repo.get_by_name("admin")
        assert admin_role is not None

        now = datetime.now(UTC)
        admin_user = User(
            id=uuid4(),
            email="admin@example.com",
            username="adminuser",
            full_name="Admin User",
            hashed_password=await _password_hasher.hash(strong_password),
            avatar_url=None,
            role_id=admin_role.id,
            role=admin_role,
            is_active=True,
            is_verified=True,
            deleted_at=None,
            last_login=None,
            created_at=now,
            updated_at=now,
        )
        await user_repo.create(admin_user)

    response = await client.post(
        "/auth/login",
        json={"identifier": "admin@example.com", "password": strong_password},
    )
    assert response.status_code == 200
    return response.json()
