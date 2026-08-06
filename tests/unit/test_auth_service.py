from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.application.services.auth_service import AuthService
from app.domain.entities.permission import Permission
from app.domain.entities.role import Role
from app.domain.entities.user import User
from app.domain.exceptions import AuthenticationError, ConflictError
from app.infrastructure.auth.in_memory_account_lockout import InMemoryAccountLockout
from app.infrastructure.auth.in_memory_rate_limiter import InMemoryRateLimiter
from app.infrastructure.email.mock_email_service import MockEmailService
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from app.infrastructure.security.jwt_token_service import JWTTokenService

USER_ROLE = Role(
    id=uuid4(),
    name="user",
    description="Standard user",
    permissions=(Permission(uuid4(), "documents.read", "Read"),),
)


def _make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password="",
        avatar_url=None,
        role_id=USER_ROLE.id,
        role=USER_ROLE,
        is_active=True,
        is_verified=False,
        deleted_at=None,
        last_login=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def auth_service() -> AuthService:
    hasher = Argon2PasswordHasher()
    user = _make_user()

    user_repo = AsyncMock()
    user_repo.email_exists.return_value = False
    user_repo.username_exists.return_value = False
    user_repo.get_by_email.return_value = None
    user_repo.get_by_username.return_value = None
    user_repo.create = AsyncMock(side_effect=lambda u: u)
    user_repo.update = AsyncMock(side_effect=lambda u: u)
    user_repo.get_by_id.return_value = user

    role_repo = AsyncMock()
    role_repo.get_by_name.return_value = USER_ROLE

    refresh_repo = AsyncMock()
    password_reset_repo = AsyncMock()
    email_verification_repo = AsyncMock()

    return AuthService(
        user_repo=user_repo,
        role_repo=role_repo,
        refresh_token_repo=refresh_repo,
        password_reset_repo=password_reset_repo,
        email_verification_repo=email_verification_repo,
        password_hasher=hasher,
        token_service=JWTTokenService(),
        email_service=MockEmailService(),
        rate_limiter=InMemoryRateLimiter(),
        account_lockout=InMemoryAccountLockout(),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_success(auth_service: AuthService) -> None:
    user = await auth_service.register(
        email="new@example.com",
        username="newuser",
        password="Str0ng!Pass",
        full_name="New User",
    )
    assert user.email == "new@example.com"
    auth_service._email_verifications.create.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_duplicate_email(auth_service: AuthService) -> None:
    auth_service._users.email_exists.return_value = True
    with pytest.raises(ConflictError, match="Email"):
        await auth_service.register("dup@example.com", "dupuser", "Str0ng!Pass", None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_invalid_credentials(auth_service: AuthService) -> None:
    with pytest.raises(AuthenticationError):
        await auth_service.login("unknown@example.com", "WrongPass1!")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_success(auth_service: AuthService) -> None:
    password = "Str0ng!Pass"
    hasher = Argon2PasswordHasher()
    hashed = await hasher.hash(password)
    user = _make_user()
    user_with_hash = replace(user, hashed_password=hashed)

    auth_service._users.get_by_email.return_value = user_with_hash
    auth_service._users.get_by_username.return_value = None

    pair = await auth_service.login("test@example.com", password)
    assert pair.access_token
    assert pair.refresh_token
