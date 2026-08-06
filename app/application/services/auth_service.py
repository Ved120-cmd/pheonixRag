"""Orchestrates all authentication flows — no FastAPI imports."""

import secrets
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.application.interfaces.account_lockout import AccountLockout
from app.application.interfaces.email_service import EmailService
from app.application.interfaces.password_hasher import PasswordHasher
from app.application.interfaces.rate_limiter import RateLimiter
from app.application.interfaces.token_service import TokenPair, TokenService
from app.application.validators.password_validator import validate_password_strength
from app.domain.entities.user import User
from app.domain.exceptions import (
    AccountLockedError,
    AuthenticationError,
    ConflictError,
    InactiveAccountError,
    NotFoundError,
    RateLimitExceededError,
)
from app.domain.repositories.email_verification_repository import EmailVerificationRepository
from app.domain.repositories.password_reset_repository import PasswordResetRepository
from app.domain.repositories.refresh_token_repository import RefreshTokenRepository
from app.domain.repositories.role_repository import RoleRepository
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.logging.logger import get_logger

logger = get_logger("phoenixrag.auth")


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        role_repo: RoleRepository,
        refresh_token_repo: RefreshTokenRepository,
        password_reset_repo: PasswordResetRepository,
        email_verification_repo: EmailVerificationRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        email_service: EmailService,
        rate_limiter: RateLimiter,
        account_lockout: AccountLockout,
        default_role_name: str = "user",
    ) -> None:
        self._users = user_repo
        self._roles = role_repo
        self._refresh_tokens = refresh_token_repo
        self._password_resets = password_reset_repo
        self._email_verifications = email_verification_repo
        self._hasher = password_hasher
        self._tokens = token_service
        self._email = email_service
        self._rate_limiter = rate_limiter
        self._lockout = account_lockout
        self._default_role_name = default_role_name

    async def register(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None,
    ) -> User:
        email = email.strip().lower()
        username = username.strip().lower()

        validate_password_strength(password)

        if await self._users.email_exists(email):
            raise ConflictError("Email already registered")
        if await self._users.username_exists(username):
            raise ConflictError("Username already taken")

        role = await self._roles.get_by_name(self._default_role_name)
        if role is None:
            raise NotFoundError("Role", self._default_role_name)

        now = datetime.now(UTC)
        user = User(
            id=uuid4(),
            email=email,
            username=username,
            full_name=full_name,
            hashed_password=await self._hasher.hash(password),
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
        created = await self._users.create(user)

        token = secrets.token_urlsafe(32)
        await self._email_verifications.create(created.id, token)
        await self._email.send_verification_email(created.email, token)

        logger.info("user_registered", extra={"user_id": str(created.id), "email": created.email})
        return created

    async def login(self, identifier: str, password: str) -> TokenPair:
        key = identifier.strip().lower()

        if not await self._rate_limiter.allow(key):
            raise RateLimitExceededError()
        if await self._lockout.is_locked(key):
            raise AccountLockedError()

        user = await self._users.get_by_email(key) or await self._users.get_by_username(key)

        valid = False
        if user is not None:
            valid = await self._hasher.verify(password, user.hashed_password)

        if user is None or not valid:
            await self._lockout.record_failure(key)
            await self._rate_limiter.record_failure(key)
            logger.warning("login_failed", extra={"identifier": key})
            raise AuthenticationError()

        if not user.is_active:
            raise InactiveAccountError()

        await self._lockout.clear(key)
        await self._rate_limiter.clear(key)

        if await self._hasher.needs_rehash(user.hashed_password):
            user = await self._users.update(
                replace(user, hashed_password=await self._hasher.hash(password))
            )

        now = datetime.now(UTC)
        user = await self._users.update(replace(user, last_login=now, updated_at=now))

        role_name = user.role.name if user.role else "user"
        pair = self._tokens.create_token_pair(user.id, role_name)
        await self._refresh_tokens.store(user.id, pair.refresh_token, pair.refresh_expires_at)

        logger.info("login_success", extra={"user_id": str(user.id)})
        return pair

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = self._tokens.decode_refresh_token(refresh_token)
        stored = await self._refresh_tokens.get_by_token(refresh_token)
        if stored is None or stored.is_revoked:
            raise AuthenticationError("Invalid refresh token")

        user = await self._users.get_by_id(payload.user_id)
        if user is None or not user.is_active or user.is_deleted:
            raise AuthenticationError("Invalid refresh token")

        await self._refresh_tokens.revoke(refresh_token)
        role_name = user.role.name if user.role else "user"
        pair = self._tokens.create_token_pair(user.id, role_name)
        await self._refresh_tokens.store(user.id, pair.refresh_token, pair.refresh_expires_at)
        return pair

    async def logout(self, refresh_token: str) -> None:
        await self._refresh_tokens.revoke(refresh_token)
        logger.info("logout_success")

    async def forgot_password(self, email: str) -> None:
        email = email.strip().lower()
        user = await self._users.get_by_email(email)
        if user is not None:
            token = secrets.token_urlsafe(32)
            await self._password_resets.create(user.id, token)
            await self._email.send_password_reset_email(user.email, token)
            logger.info("password_reset_requested", extra={"user_id": str(user.id)})

    async def reset_password(self, token: str, new_password: str) -> None:
        validate_password_strength(new_password)
        reset = await self._password_resets.get_valid(token)
        if reset is None:
            raise AuthenticationError("Invalid or expired reset token")

        user = await self._users.get_by_id(reset.user_id)
        if user is None:
            raise AuthenticationError("Invalid or expired reset token")

        updated = replace(
            user,
            hashed_password=await self._hasher.hash(new_password),
            updated_at=datetime.now(UTC),
        )
        await self._users.update(updated)
        await self._password_resets.mark_used(token)
        await self._refresh_tokens.revoke_all_for_user(user.id)
        logger.info("password_reset_completed", extra={"user_id": str(user.id)})

    async def verify_email(self, token: str) -> None:
        record = await self._email_verifications.get_valid(token)
        if record is None:
            raise AuthenticationError("Invalid or expired verification token")

        user = await self._users.get_by_id(record.user_id)
        if user is None:
            raise AuthenticationError("Invalid or expired verification token")

        await self._users.update(
            replace(user, is_verified=True, updated_at=datetime.now(UTC))
        )
        await self._email_verifications.mark_used(token)
        logger.info("email_verified", extra={"user_id": str(user.id)})

    async def get_user_from_access_token(self, token: str) -> User:
        payload = self._tokens.decode_access_token(token)
        user = await self._users.get_by_id(payload.user_id)
        if user is None or not user.is_active or user.is_deleted:
            raise AuthenticationError("Invalid token")
        return user
