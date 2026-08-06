import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.application.interfaces.token_service import TokenPair, TokenPayload, TokenService
from app.config.settings import get_settings
from app.domain.exceptions import AuthenticationError

settings = get_settings()


class JWTTokenService(TokenService):
    def create_token_pair(self, user_id: UUID, role_name: str) -> TokenPair:
        now = datetime.now(UTC)
        access_exp = now + timedelta(minutes=settings.access_token_expire_minutes)
        refresh_exp = now + timedelta(days=settings.refresh_token_expire_days)

        access = jwt.encode(
            {
                "sub": str(user_id),
                "role": role_name,
                "type": "access",
                "exp": access_exp,
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        refresh = jwt.encode(
            {
                "sub": str(user_id),
                "type": "refresh",
                "exp": refresh_exp,
                "jti": secrets.token_hex(16),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
        )

    def decode_access_token(self, token: str) -> TokenPayload:
        return self._decode(token, expected_type="access")

    def decode_refresh_token(self, token: str) -> TokenPayload:
        return self._decode(token, expected_type="refresh")

    def _decode(self, token: str, expected_type: str) -> TokenPayload:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            if payload.get("type") != expected_type:
                raise AuthenticationError("Invalid token")
            return TokenPayload(
                user_id=UUID(payload["sub"]),
                role_name=payload.get("role"),
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid token") from exc
