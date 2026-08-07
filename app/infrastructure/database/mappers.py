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


from app.domain.entities.document import Document
from app.infrastructure.database.models.document import DocumentModel


def document_to_entity(model: DocumentModel) -> Document:
    if model is None:
        return None
    import json

    metadata = json.loads(model.meta_payload) if model.meta_payload else None
    return Document(
        id=model.id,
        filename=model.filename,
        mime_type=model.mime_type,
        size=model.size,
        pages=model.pages,
        owner_id=model.owner_id,
        version=model.version,
        storage_path=model.storage_path,
        checksum=model.checksum,
        status=model.status,
        metadata=metadata,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )


def document_to_model(entity: Document) -> DocumentModel:
    import json

    return DocumentModel(
        id=entity.id,
        filename=entity.filename,
        mime_type=entity.mime_type,
        size=entity.size,
        pages=entity.pages,
        owner_id=entity.owner_id,
        version=entity.version,
        storage_path=entity.storage_path,
        checksum=entity.checksum,
        status=entity.status,
        meta_payload=json.dumps(entity.metadata) if entity.metadata else None,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        deleted_at=entity.deleted_at,
    )
