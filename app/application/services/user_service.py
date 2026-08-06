"""User profile operations for authenticated users."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.application.interfaces.password_hasher import PasswordHasher
from app.application.validators.password_validator import validate_password_strength
from app.domain.entities.user import User
from app.domain.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.logging.logger import get_logger

logger = get_logger("phoenixrag.users")


class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._users = user_repo
        self._refresh_tokens = refresh_token_repo
        self._hasher = password_hasher

    async def get_me(self, user_id: UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User", user_id)
        return user

    async def update_me(
        self,
        user_id: UUID,
        *,
        full_name: str | None = None,
        avatar_url: str | None = None,
        username: str | None = None,
    ) -> User:
        user = await self.get_me(user_id)
        updates: dict[str, object] = {"updated_at": datetime.now(UTC)}

        if full_name is not None:
            updates["full_name"] = full_name
        if avatar_url is not None:
            updates["avatar_url"] = avatar_url
        if username is not None:
            username = username.strip().lower()
            if username != user.username and await self._users.username_exists(username):
                raise ConflictError("Username already taken")
            updates["username"] = username

        return await self._users.update(replace(user, **updates))

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> None:
        user = await self.get_me(user_id)
        if not await self._hasher.verify(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")

        validate_password_strength(new_password)
        updated = replace(
            user,
            hashed_password=await self._hasher.hash(new_password),
            updated_at=datetime.now(UTC),
        )
        await self._users.update(updated)
        await self._refresh_tokens.revoke_all_for_user(user_id)
        logger.info("password_changed", extra={"user_id": str(user_id)})

    async def deactivate_account(self, user_id: UUID) -> None:
        user = await self.get_me(user_id)
        updated = replace(user, is_active=False, updated_at=datetime.now(UTC))
        await self._users.update(updated)
        await self._refresh_tokens.revoke_all_for_user(user_id)
        logger.info("account_deactivated", extra={"user_id": str(user_id)})

    async def delete_account(self, user_id: UUID) -> None:
        await self.get_me(user_id)
        await self._refresh_tokens.revoke_all_for_user(user_id)
        await self._users.delete(user_id)
        logger.info("account_soft_deleted", extra={"user_id": str(user_id)})
