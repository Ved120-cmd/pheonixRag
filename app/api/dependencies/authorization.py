from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import get_current_user
from app.domain.entities.user import User


def RequireRole(role_name: str) -> Callable[..., User]:
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role is None or user.role.name != role_name:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return _checker


def RequirePermission(permission_name: str) -> Callable[..., User]:
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_permission(permission_name):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return _checker
