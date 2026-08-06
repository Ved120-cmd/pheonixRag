from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.infrastructure.database.repositories.role_repository import SQLAlchemyRoleRepository
from app.infrastructure.database.repositories.user_repository import SQLAlchemyUserRepository
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_repository_crud(seeded_session: AsyncSession) -> None:
    role_repo = SQLAlchemyRoleRepository(seeded_session)
    user_repo = SQLAlchemyUserRepository(seeded_session)
    hasher = Argon2PasswordHasher()

    role = await role_repo.get_by_name("user")
    assert role is not None

    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email="repo@example.com",
        username="repouser",
        full_name="Repo User",
        hashed_password=await hasher.hash("Str0ng!Pass"),
        avatar_url=None,
        role_id=role.id,
        role=role,
        is_active=True,
        is_verified=False,
        deleted_at=None,
        last_login=None,
        created_at=now,
        updated_at=now,
    )

    created = await user_repo.create(user)
    assert created.email == "repo@example.com"

    fetched = await user_repo.get_by_email("repo@example.com")
    assert fetched is not None
    assert fetched.username == "repouser"

    assert await user_repo.email_exists("repo@example.com")
    assert await user_repo.username_exists("repouser")

    listed = await user_repo.list_all()
    assert len(listed) >= 1

    await user_repo.delete(created.id)
    assert await user_repo.get_by_id(created.id) is None
    assert await user_repo.email_exists("repo@example.com")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_soft_delete_preserves_email(seeded_session: AsyncSession) -> None:
    role_repo = SQLAlchemyRoleRepository(seeded_session)
    user_repo = SQLAlchemyUserRepository(seeded_session)
    hasher = Argon2PasswordHasher()

    role = await role_repo.get_by_name("user")
    assert role is not None

    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email="softdelete@example.com",
        username="softdeleteuser",
        full_name="Soft Delete User",
        hashed_password=await hasher.hash("Str0ng!Pass"),
        avatar_url=None,
        role_id=role.id,
        role=role,
        is_active=True,
        is_verified=False,
        deleted_at=None,
        last_login=None,
        created_at=now,
        updated_at=now,
    )

    created = await user_repo.create(user)
    await user_repo.delete(created.id)

    assert await user_repo.get_by_id(created.id) is None
    assert await user_repo.get_by_email("softdelete@example.com") is None
    assert await user_repo.email_exists("softdelete@example.com")
