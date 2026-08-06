from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies.services import get_auth_service
from app.application.services.auth_service import AuthService
from app.domain.entities.user import User
from app.domain.exceptions import AuthenticationError, InactiveAccountError

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        return await auth_service.get_user_from_access_token(credentials.credentials)
    except (AuthenticationError, InactiveAccountError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, exc.message) from exc
