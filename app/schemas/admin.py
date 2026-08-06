from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class AdminUserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class ChangeRoleRequest(BaseModel):
    role: str = Field(min_length=1, max_length=50)


class ChangeStatusRequest(BaseModel):
    is_active: bool
