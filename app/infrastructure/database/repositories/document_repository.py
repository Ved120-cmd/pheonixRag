from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.document import Document
from app.domain.repositories.document_repository import DocumentRepository
from app.infrastructure.database.mappers import document_to_entity, document_to_model
from app.infrastructure.database.models.document import DocumentModel


class SQLAlchemyDocumentRepository(DocumentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _active_only() -> bool:
        return DocumentModel.deleted_at.is_(None)

    async def create(self, document: Document) -> Document:
        model = document_to_model(document)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return document_to_entity(model)

    async def get_by_id(self, document_id: UUID) -> Document | None:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id, self._active_only())
        )
        model = result.scalar_one_or_none()
        return document_to_entity(model) if model else None

    async def update(self, document: Document) -> Document:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.id == document.id)
        )
        model = result.scalar_one()
        model.filename = document.filename
        model.mime_type = document.mime_type
        model.size = document.size
        model.pages = document.pages
        model.owner_id = document.owner_id
        model.version = document.version
        model.storage_path = document.storage_path
        model.checksum = document.checksum
        model.status = document.status
        model.metadata = document.metadata
        model.deleted_at = document.deleted_at
        await self._session.commit()
        await self._session.refresh(model)
        return document_to_entity(model)

    async def delete(self, document_id: UUID) -> None:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id, self._active_only())
        )
        model = result.scalar_one_or_none()
        if model is None:
            return
        now = datetime.now(UTC)
        model.deleted_at = now
        model.updated_at = now
        await self._session.commit()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Document]:
        result = await self._session.execute(
            select(DocumentModel)
            .where(self._active_only())
            .offset(skip)
            .limit(limit)
            .order_by(DocumentModel.created_at.desc())
        )
        return [document_to_entity(m) for m in result.scalars().all()]

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(DocumentModel).where(self._active_only())
        )
        return result.scalar_one() or 0

    async def find_by_checksum(self, checksum: str) -> Document | None:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.checksum == checksum, self._active_only())
        )
        model = result.scalar_one_or_none()
        return document_to_entity(model) if model else None
