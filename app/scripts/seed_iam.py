"""Seed default roles, permissions, and optional bootstrap admin user."""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.infrastructure.database.models.permission import PermissionModel
from app.infrastructure.database.models.role import RoleModel
from app.infrastructure.database.models.role_permission import RolePermissionModel
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher

settings = get_settings()
_password_hasher = Argon2PasswordHasher()

PERMISSIONS = [
    ("documents.read", "Read documents"),
    ("documents.write", "Write documents"),
    ("admin.manage", "Manage users and system settings"),
    ("chat.use", "Use chat features"),
]

ROLES = {
    "admin": {
        "description": "Full system administrator",
        "permissions": ["documents.read", "documents.write", "admin.manage", "chat.use"],
    },
    "user": {
        "description": "Standard user",
        "permissions": ["documents.read", "chat.use"],
    },
}


async def seed_iam(session: AsyncSession) -> None:
    permission_map: dict[str, uuid.UUID] = {}

    for name, description in PERMISSIONS:
        result = await session.execute(select(PermissionModel).where(PermissionModel.name == name))
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = PermissionModel(id=uuid.uuid4(), name=name, description=description)
            session.add(perm)
        permission_map[name] = perm.id

    await session.flush()

    for role_name, config in ROLES.items():
        result = await session.execute(select(RoleModel).where(RoleModel.name == role_name))
        role = result.scalar_one_or_none()
        if role is None:
            role = RoleModel(
                id=uuid.uuid4(),
                name=role_name,
                description=config["description"],
            )
            session.add(role)
            await session.flush()

        for perm_name in config["permissions"]:
            perm_id = permission_map[perm_name]
            result = await session.execute(
                select(RolePermissionModel).where(
                    RolePermissionModel.role_id == role.id,
                    RolePermissionModel.permission_id == perm_id,
                )
            )
            if result.scalar_one_or_none() is None:
                session.add(RolePermissionModel(role_id=role.id, permission_id=perm_id))

    await session.commit()


async def seed_admin_user(session: AsyncSession) -> None:
    """Create bootstrap admin account if it does not exist."""
    result = await session.execute(
        select(UserModel).where(UserModel.email == settings.bootstrap_admin_email)
    )
    if result.scalar_one_or_none() is not None:
        return

    result = await session.execute(select(RoleModel).where(RoleModel.name == "admin"))
    admin_role = result.scalar_one_or_none()
    if admin_role is None:
        return

    now = datetime.now(UTC)
    admin = UserModel(
        id=uuid.uuid4(),
        email=settings.bootstrap_admin_email,
        username=settings.bootstrap_admin_username,
        full_name="System Administrator",
        hashed_password=await _password_hasher.hash(settings.bootstrap_admin_password),
        avatar_url=None,
        role_id=admin_role.id,
        is_active=True,
        is_verified=True,
        last_login=None,
        created_at=now,
        updated_at=now,
    )
    session.add(admin)
    await session.commit()


async def main() -> None:
    from app.infrastructure.database.base import Base
    from app.infrastructure.database.session import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_iam(session)
        await seed_admin_user(session)
        print("IAM seed completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())

