from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.authorization import RequirePermission
from app.api.dependencies.services import get_admin_service
from app.api.mappers import user_to_response
from app.application.services.admin_service import AdminService
from app.domain.entities.user import User
from app.schemas.admin import AdminUserListResponse, ChangeRoleRequest, ChangeStatusRequest
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    _admin: User = Depends(RequirePermission("admin.manage")),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminUserListResponse:
    users, total = await admin_service.list_users(skip=skip, limit=limit)
    return AdminUserListResponse(
        users=[user_to_response(u) for u in users],
        total=total,
    )


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: UUID,
    body: ChangeRoleRequest,
    admin: User = Depends(RequirePermission("admin.manage")),
    admin_service: AdminService = Depends(get_admin_service),
) -> UserResponse:
    updated = await admin_service.change_user_role(admin.id, user_id, body.role)
    return user_to_response(updated)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
async def change_user_status(
    user_id: UUID,
    body: ChangeStatusRequest,
    admin: User = Depends(RequirePermission("admin.manage")),
    admin_service: AdminService = Depends(get_admin_service),
) -> UserResponse:
    updated = await admin_service.change_user_status(admin.id, user_id, body.is_active)
    return user_to_response(updated)
