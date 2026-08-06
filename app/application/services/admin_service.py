"""Admin operations for user management."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.domain.entities.user import User
from app.domain.exceptions import AuthorizationError, NotFoundError
from app.domain.repositories.role_repository import RoleRepository
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.logging.logger import get_logger

logger = get_logger("phoenixrag.admin")


class AdminService:
    def __init__(
        self,
        user_repo: UserRepository,
        role_repo: RoleRepository,
    ) -> None:
        self._users = user_repo
        self._roles = role_repo

    async def list_users(self, skip: int = 0, limit: int = 100) -> tuple[list[User], int]:
        users = await self._users.list_all(skip=skip, limit=limit)
        total = await self._users.count()
        return users, total

    async def change_user_role(
        self, admin_id: UUID, user_id: UUID, role_name: str
    ) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User", user_id)

        role = await self._roles.get_by_name(role_name)
        if role is None:
            raise NotFoundError("Role", role_name)

        updated = await self._users.update(
            replace(user, role_id=role.id, role=role, updated_at=datetime.now(UTC))
        )
        logger.info(
            "role_changed",
            extra={
                "admin_id": str(admin_id),
                "target_user_id": str(user_id),
                "new_role": role_name,
            },
        )
        return updated

    async def change_user_status(
        self, admin_id: UUID, user_id: UUID, is_active: bool
    ) -> User:
        if admin_id == user_id and not is_active:
            raise AuthorizationError("Cannot deactivate your own account")

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User", user_id)

        updated = await self._users.update(
            replace(user, is_active=is_active, updated_at=datetime.now(UTC))
        )
        logger.info(
            "user_status_changed",
            extra={
                "admin_id": str(admin_id),
                "target_user_id": str(user_id),
                "is_active": is_active,
            },
        )
        return updated
