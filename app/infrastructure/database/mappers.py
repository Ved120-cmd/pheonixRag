import json

from app.domain.entities.chunk import Chunk
from app.domain.entities.permission import Permission
from app.domain.entities.role import Role
from app.domain.entities.token import (
    EmailVerificationRecord,
    PasswordResetRecord,
    RefreshTokenRecord,
)
from app.domain.entities.user import User
from app.infrastructure.database.models.email_verification_token import EmailVerificationTokenModel
from app.infrastructure.database.models.password_reset_token import PasswordResetTokenModel
from app.infrastructure.database.models.permission import PermissionModel
from app.infrastructure.database.models.refresh_token import RefreshTokenModel
from app.infrastructure.database.models.role import RoleModel
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.models.chunk import ChunkModel


def chunk_to_entity(model: ChunkModel) -> Chunk:
    return Chunk(
        id=model.id,
        document_id=model.document_id,
        document_version=model.document_version,
        parent_chunk_id=model.parent_chunk_id,
        chunk_index=model.chunk_index,
        text=model.text,
        token_count=model.token_count,
        character_count=model.character_count,
        page_numbers=json.loads(model.page_numbers or "[]"),
        section_path=json.loads(model.section_path or "[]"),
        document_metadata=json.loads(model.document_metadata or "{}"),
        strategy=model.strategy,
        configuration=json.loads(model.configuration),
        content_hash=model.content_hash,
        is_active=model.is_active,
        created_at=model.created_at,
    )


def chunk_to_model(entity: Chunk) -> ChunkModel:
    return ChunkModel(
        id=entity.id,
        document_id=entity.document_id,
        document_version=entity.document_version,
        parent_chunk_id=entity.parent_chunk_id,
        chunk_index=entity.chunk_index,
        text=entity.text,
        token_count=entity.token_count,
        character_count=entity.character_count,
        page_numbers=json.dumps(entity.page_numbers),
        section_path=json.dumps(entity.section_path),
        document_metadata=json.dumps(entity.document_metadata),
        strategy=entity.strategy,
        configuration=json.dumps(entity.configuration, sort_keys=True),
        content_hash=entity.content_hash,
        is_active=entity.is_active,
        created_at=entity.created_at,
    )


def permission_to_entity(model: PermissionModel) -> Permission:
    return Permission(id=model.id, name=model.name, description=model.description)


def role_to_entity(model: RoleModel) -> Role:
    permissions = tuple(
        permission_to_entity(rp.permission) for rp in model.role_permissions if rp.permission
    )
    return Role(
        id=model.id,
        name=model.name,
        description=model.description,
        permissions=permissions,
    )


def user_to_entity(model: UserModel) -> User:
    role = role_to_entity(model.role) if model.role else None
    return User(
        id=model.id,
        email=model.email,
        username=model.username,
        full_name=model.full_name,
        hashed_password=model.hashed_password,
        avatar_url=model.avatar_url,
        role_id=model.role_id,
        role=role,
        is_active=model.is_active,
        is_verified=model.is_verified,
        deleted_at=model.deleted_at,
        last_login=model.last_login,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def user_to_model(entity: User) -> UserModel:
    return UserModel(
        id=entity.id,
        email=entity.email,
        username=entity.username,
        full_name=entity.full_name,
        hashed_password=entity.hashed_password,
        avatar_url=entity.avatar_url,
        role_id=entity.role_id,
        is_active=entity.is_active,
        is_verified=entity.is_verified,
        deleted_at=entity.deleted_at,
        last_login=entity.last_login,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def refresh_token_to_entity(model: RefreshTokenModel) -> RefreshTokenRecord:
    return RefreshTokenRecord(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        created_at=model.created_at,
    )


def password_reset_to_entity(model: PasswordResetTokenModel) -> PasswordResetRecord:
    return PasswordResetRecord(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        used_at=model.used_at,
        created_at=model.created_at,
    )


def email_verification_to_entity(model: EmailVerificationTokenModel) -> EmailVerificationRecord:
    return EmailVerificationRecord(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        used_at=model.used_at,
        created_at=model.created_at,
    )
