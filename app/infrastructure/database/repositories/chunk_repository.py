from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.chunk import Chunk
from app.domain.repositories.chunk_repository import ChunkRepository
from app.infrastructure.database.mappers import chunk_to_entity, chunk_to_model
from app.infrastructure.database.models.chunk import ChunkModel


class SQLAlchemyChunkRepository(ChunkRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_active(self, document_id: UUID, version: int, chunks: list[Chunk]) -> None:
        await self._session.execute(
            update(ChunkModel)
            .where(ChunkModel.document_id == document_id, ChunkModel.is_active.is_(True))
            .values(is_active=False)
        )
        self._session.add_all(chunk_to_model(chunk) for chunk in chunks)
        await self._session.commit()

    async def list_active(self, document_id: UUID, version: int | None = None) -> list[Chunk]:
        query = select(ChunkModel).where(
            ChunkModel.document_id == document_id, ChunkModel.is_active.is_(True)
        )
        if version is not None:
            query = query.where(ChunkModel.document_version == version)
        result = await self._session.execute(query.order_by(ChunkModel.chunk_index))
        return [chunk_to_entity(model) for model in result.scalars().all()]

    async def get(self, chunk_id: UUID) -> Chunk | None:
        result = await self._session.execute(select(ChunkModel).where(ChunkModel.id == chunk_id))
        model = result.scalar_one_or_none()
        return chunk_to_entity(model) if model else None

    async def delete_document(self, document_id: UUID) -> int:
        result = await self._session.execute(
            delete(ChunkModel).where(ChunkModel.document_id == document_id)
        )
        await self._session.commit()
        return result.rowcount or 0
