from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.chunk import Chunk
from app.domain.entities.indexing import DocumentIndexState, IndexSource, IndexingJob
from app.domain.repositories.indexing_repository import IndexingRepository
from app.infrastructure.database.mappers import chunk_to_entity
from app.infrastructure.database.models.chunk import ChunkModel
from app.infrastructure.database.models.document import DocumentModel
from app.infrastructure.database.models.indexing import DocumentIndexStateModel, IndexingJobModel


def _job_entity(model: IndexingJobModel) -> IndexingJob:
    return IndexingJob(
        id=model.id,
        tenant_id=model.tenant_id,
        document_id=model.document_id,
        document_version=model.document_version,
        chunk_set_fingerprint=model.chunk_set_fingerprint,
        collection_name=model.collection_name,
        embedding_fingerprint=model.embedding_fingerprint,
        model_name=model.model_name,
        model_version=model.model_version,
        status=model.status,
        total_vectors=model.total_vectors,
        processed_vectors=model.processed_vectors,
        failed_vectors=model.failed_vectors,
        retries=model.retries,
        duration_seconds=model.duration_seconds,
        error=model.error,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _state_entity(model: DocumentIndexStateModel) -> DocumentIndexState:
    return DocumentIndexState(
        tenant_id=model.tenant_id,
        document_id=model.document_id,
        active_document_version=model.active_document_version,
        active_collection=model.active_collection,
        active_embedding_fingerprint=model.active_embedding_fingerprint,
        active_chunk_set_fingerprint=model.active_chunk_set_fingerprint,
        updated_at=model.updated_at,
    )


class SQLAlchemyIndexingRepository(IndexingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_index_source(
        self, tenant_id: UUID, document_id: UUID, include_deleted: bool = False
    ) -> IndexSource | None:
        filters = [DocumentModel.id == document_id, DocumentModel.owner_id == tenant_id]
        if not include_deleted:
            filters.append(DocumentModel.deleted_at.is_(None))
        document_result = await self._session.execute(select(DocumentModel).where(*filters))
        document = document_result.scalar_one_or_none()
        if document is None:
            return None
        metadata = json.loads(document.meta_payload or "{}")
        tags = metadata.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        return IndexSource(
            tenant_id=tenant_id,
            document_id=document_id,
            document_version=document.version,
            document_type=document.mime_type,
            tags=tuple(str(tag)[:128] for tag in tags[:64] if isinstance(tag, str)),
            document_created_at=document.created_at,
        )

    async def count_index_chunks(self, tenant_id: UUID, document_id: UUID, version: int) -> int:
        result = await self._session.execute(
            select(func.count(ChunkModel.id))
            .join(DocumentModel, DocumentModel.id == ChunkModel.document_id)
            .where(
                DocumentModel.id == document_id,
                DocumentModel.owner_id == tenant_id,
                DocumentModel.deleted_at.is_(None),
                DocumentModel.version == version,
                ChunkModel.document_version == version,
                ChunkModel.is_active.is_(True),
            )
        )
        return result.scalar_one()

    async def list_index_chunks(
        self, tenant_id: UUID, document_id: UUID, version: int, offset: int, limit: int
    ) -> list[Chunk]:
        if offset < 0 or limit <= 0:
            raise ValueError("chunk page offset must be non-negative and limit must be positive")
        result = await self._session.execute(
            select(ChunkModel)
            .join(DocumentModel, DocumentModel.id == ChunkModel.document_id)
            .where(
                DocumentModel.id == document_id,
                DocumentModel.owner_id == tenant_id,
                DocumentModel.deleted_at.is_(None),
                DocumentModel.version == version,
                ChunkModel.document_version == version,
                ChunkModel.is_active.is_(True),
            )
            .order_by(ChunkModel.chunk_index)
            .offset(offset)
            .limit(limit)
        )
        return [chunk_to_entity(row) for row in result.scalars().all()]

    async def chunk_set_fingerprint(self, tenant_id: UUID, document_id: UUID, version: int) -> str:
        result = await self._session.execute(
            select(ChunkModel.id, ChunkModel.content_hash)
            .join(DocumentModel, DocumentModel.id == ChunkModel.document_id)
            .where(
                DocumentModel.id == document_id,
                DocumentModel.owner_id == tenant_id,
                DocumentModel.deleted_at.is_(None),
                DocumentModel.version == version,
                ChunkModel.document_version == version,
                ChunkModel.is_active.is_(True),
            )
            .order_by(ChunkModel.chunk_index)
        )
        digest = hashlib.sha256()
        for chunk_id, content_hash in result.all():
            digest.update(f"{chunk_id}:{content_hash}\n".encode("utf-8"))
        return digest.hexdigest()

    async def create_or_get_job(self, job: IndexingJob) -> IndexingJob:
        key_material = (
            f"{job.tenant_id}:{job.document_id}:{job.document_version}:"
            f"{job.chunk_set_fingerprint}:{job.embedding_fingerprint}"
        )
        idempotency_key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        dialect = self._session.bind.dialect.name if self._session.bind else "postgresql"
        insert = sqlite_insert if dialect == "sqlite" else postgres_insert
        statement = insert(IndexingJobModel).values(
            id=job.id,
            idempotency_key=idempotency_key,
            tenant_id=job.tenant_id,
            document_id=job.document_id,
            document_version=job.document_version,
            chunk_set_fingerprint=job.chunk_set_fingerprint,
            collection_name=job.collection_name,
            embedding_fingerprint=job.embedding_fingerprint,
            model_name=job.model_name,
            model_version=job.model_version,
            status=job.status,
            total_vectors=job.total_vectors,
        ).on_conflict_do_nothing(index_elements=["idempotency_key"])
        await self._session.execute(statement)
        await self._session.commit()
        result = await self._session.execute(
            select(IndexingJobModel).where(IndexingJobModel.idempotency_key == idempotency_key)
        )
        model = result.scalar_one()
        if model.status in ("failed", "partial", "deleting", "deleted", "cancelled"):
            model.status = "pending"
            model.total_vectors = job.total_vectors
            model.processed_vectors = 0
            model.failed_vectors = 0
            model.error = None
            model.updated_at = datetime.now(UTC)
            await self._session.commit()
            await self._session.refresh(model)
        return _job_entity(model)

    async def get_job(self, job_id: UUID) -> IndexingJob | None:
        model = await self._session.get(IndexingJobModel, job_id)
        return _job_entity(model) if model else None

    async def update_job(self, job: IndexingJob) -> IndexingJob:
        model = await self._session.get(IndexingJobModel, job.id)
        if model is None:
            raise ValueError("indexing job not found")
        model.status = job.status
        model.total_vectors = job.total_vectors
        model.processed_vectors = job.processed_vectors
        model.failed_vectors = job.failed_vectors
        model.retries = job.retries
        model.duration_seconds = job.duration_seconds
        model.error = job.error
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return _job_entity(model)

    async def cancel_job(self, tenant_id: UUID, job_id: UUID) -> IndexingJob | None:
        await self._session.execute(
            update(IndexingJobModel)
            .where(
                IndexingJobModel.id == job_id,
                IndexingJobModel.tenant_id == tenant_id,
                IndexingJobModel.status.in_(("pending", "indexing", "partial")),
            )
            .values(status="cancelled", updated_at=datetime.now(UTC))
        )
        await self._session.commit()
        model = await self._session.get(IndexingJobModel, job_id)
        return _job_entity(model) if model and model.tenant_id == tenant_id else None

    async def latest_job(self, tenant_id: UUID, document_id: UUID) -> IndexingJob | None:
        result = await self._session.execute(
            select(IndexingJobModel)
            .where(IndexingJobModel.tenant_id == tenant_id, IndexingJobModel.document_id == document_id)
            .order_by(IndexingJobModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _job_entity(model) if model else None

    async def publish_version(self, state: DocumentIndexState, job: IndexingJob) -> DocumentIndexState:
        latest_result = await self._session.execute(
            select(IndexingJobModel)
            .where(
                IndexingJobModel.tenant_id == state.tenant_id,
                IndexingJobModel.document_id == state.document_id,
            )
            .order_by(IndexingJobModel.created_at.desc())
            .limit(1)
        )
        latest_job = latest_result.scalar_one_or_none()
        if (
            latest_job is None
            or latest_job.id != job.id
            or latest_job.chunk_set_fingerprint != state.active_chunk_set_fingerprint
        ):
            raise ValueError("a newer indexing request superseded this job")
        document_result = await self._session.execute(
            select(DocumentModel)
            .where(
                DocumentModel.id == state.document_id,
                DocumentModel.owner_id == state.tenant_id,
                DocumentModel.version == state.active_document_version,
                DocumentModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if document_result.scalar_one_or_none() is None:
            raise ValueError("document version changed before indexing could be published")
        current_chunk_set = await self.chunk_set_fingerprint(
            state.tenant_id, state.document_id, state.active_document_version
        )
        if current_chunk_set != state.active_chunk_set_fingerprint:
            raise ValueError("active chunks changed before indexing could be published")
        latest_job.status = "indexed"
        latest_job.processed_vectors = job.processed_vectors
        latest_job.failed_vectors = job.failed_vectors
        latest_job.retries = job.retries
        latest_job.duration_seconds = job.duration_seconds
        latest_job.error = None
        latest_job.updated_at = datetime.now(UTC)
        dialect = self._session.bind.dialect.name if self._session.bind else "postgresql"
        insert = sqlite_insert if dialect == "sqlite" else postgres_insert
        statement = insert(DocumentIndexStateModel).values(
            tenant_id=state.tenant_id,
            document_id=state.document_id,
            active_document_version=state.active_document_version,
            active_chunk_set_fingerprint=state.active_chunk_set_fingerprint,
            active_collection=state.active_collection,
            active_embedding_fingerprint=state.active_embedding_fingerprint,
            updated_at=datetime.now(UTC),
        ).on_conflict_do_update(
            index_elements=["document_id"],
            set_={
                "tenant_id": state.tenant_id,
                "active_document_version": state.active_document_version,
                "active_chunk_set_fingerprint": state.active_chunk_set_fingerprint,
                "active_collection": state.active_collection,
                "active_embedding_fingerprint": state.active_embedding_fingerprint,
                "updated_at": datetime.now(UTC),
            },
        )
        await self._session.execute(statement)
        await self._session.commit()
        model = await self._session.get(DocumentIndexStateModel, state.document_id)
        return _state_entity(model)

    async def get_document_state(self, tenant_id: UUID, document_id: UUID) -> DocumentIndexState | None:
        result = await self._session.execute(
            select(DocumentIndexStateModel).where(
                DocumentIndexStateModel.tenant_id == tenant_id,
                DocumentIndexStateModel.document_id == document_id,
            )
        )
        model = result.scalar_one_or_none()
        return _state_entity(model) if model else None

    async def clear_document_state(self, tenant_id: UUID, document_id: UUID) -> None:
        await self._session.execute(
            delete(DocumentIndexStateModel).where(
                DocumentIndexStateModel.tenant_id == tenant_id,
                DocumentIndexStateModel.document_id == document_id,
            )
        )
        await self._session.commit()

    async def active_versions(self, tenant_id: UUID) -> dict[UUID, tuple[int, str]]:
        result = await self._session.execute(
            select(
                DocumentIndexStateModel.document_id,
                DocumentIndexStateModel.active_document_version,
                DocumentIndexStateModel.active_chunk_set_fingerprint,
            )
            .where(
                DocumentIndexStateModel.tenant_id == tenant_id,
                DocumentIndexStateModel.active_document_version.is_not(None),
            )
        )
        return {
            document_id: (version, chunk_fingerprint)
            for document_id, version, chunk_fingerprint in result.all()
            if chunk_fingerprint is not None
        }

    async def collection_is_active(self, collection_name: str) -> bool:
        result = await self._session.execute(
            select(DocumentIndexStateModel.document_id)
            .where(DocumentIndexStateModel.active_collection == collection_name)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def collection_has_live_jobs(self, collection_name: str) -> bool:
        result = await self._session.execute(
            select(IndexingJobModel.id)
            .where(
                IndexingJobModel.collection_name == collection_name,
                IndexingJobModel.status.in_(("pending", "indexing")),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_document_jobs(self, tenant_id: UUID, document_id: UUID) -> list[IndexingJob]:
        result = await self._session.execute(
            select(IndexingJobModel)
            .where(IndexingJobModel.tenant_id == tenant_id, IndexingJobModel.document_id == document_id)
            .order_by(IndexingJobModel.created_at.desc())
        )
        return [_job_entity(model) for model in result.scalars().all()]

    async def statistics(self, tenant_id: UUID) -> dict[str, int]:
        result = await self._session.execute(
            select(IndexingJobModel.status, func.count(IndexingJobModel.id))
            .where(IndexingJobModel.tenant_id == tenant_id)
            .group_by(IndexingJobModel.status)
        )
        return {status: count for status, count in result.all()}