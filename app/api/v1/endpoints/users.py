from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.services import get_user_service
from app.api.mappers import user_to_response
from app.application.services.user_service import UserService
from app.domain.entities.user import User
from app.schemas.auth import MessageResponse
from app.schemas.user import ChangePasswordRequest, UpdateUserRequest, UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return user_to_response(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateUserRequest,
    user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    updated = await user_service.update_me(
        user.id,
        full_name=body.full_name,
        avatar_url=body.avatar_url,
        username=body.username,
    )
    return user_to_response(updated)


@router.patch("/me/password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> MessageResponse:
    await user_service.change_password(user.id, body.current_password, body.new_password)
    return MessageResponse(message="Password changed successfully")


@router.delete("/me", response_model=MessageResponse)
async def delete_me(
    user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> MessageResponse:
    await user_service.delete_account(user.id)
    return MessageResponse(message="Account deleted successfully")
