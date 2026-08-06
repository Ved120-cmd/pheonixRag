from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.config.settings import get_settings
from app.domain.exceptions import AuthenticationError
from app.infrastructure.security.jwt_token_service import JWTTokenService

settings = get_settings()


@pytest.mark.unit
def test_jwt_create_and_decode_access_token() -> None:
    service = JWTTokenService()
    user_id = uuid4()
    pair = service.create_token_pair(user_id, "user")

    payload = service.decode_access_token(pair.access_token)
    assert payload.user_id == user_id
    assert payload.role_name == "user"


@pytest.mark.unit
def test_jwt_create_and_decode_refresh_token() -> None:
    service = JWTTokenService()
    user_id = uuid4()
    pair = service.create_token_pair(user_id, "admin")

    payload = service.decode_refresh_token(pair.refresh_token)
    assert payload.user_id == user_id


@pytest.mark.unit
def test_jwt_rejects_wrong_token_type() -> None:
    service = JWTTokenService()
    user_id = uuid4()
    pair = service.create_token_pair(user_id, "user")

    with pytest.raises(AuthenticationError):
        service.decode_refresh_token(pair.access_token)


@pytest.mark.unit
def test_jwt_rejects_expired_token() -> None:
    user_id = uuid4()
    expired = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "role": "user",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    service = JWTTokenService()
    with pytest.raises(AuthenticationError):
        service.decode_access_token(expired)
