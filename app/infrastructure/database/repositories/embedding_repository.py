from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.embedding import EmbeddingJob, EmbeddingRecord
from app.domain.repositories.embedding_repository import EmbeddingRepository
from app.infrastructure.database.models.embedding import EmbeddingJobModel, EmbeddingRecordModel


def _job_entity(model: EmbeddingJobModel) -> EmbeddingJob:
    return EmbeddingJob(
        id=model.id,
        document_id=model.document_id,
        document_version=model.document_version,
        configuration_fingerprint=model.configuration_fingerprint,
        model_name=model.model_name,
        model_version=model.model_version,
        status=model.status,
        total_chunks=model.total_chunks,
        completed_chunks=model.completed_chunks,
        failed_chunks=model.failed_chunks,
        retry_count=model.retry_count,
        error=model.error,
        processing_duration=model.processing_duration,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _record_entity(model: EmbeddingRecordModel) -> EmbeddingRecord:
    return EmbeddingRecord(
        id=model.id,
        chunk_id=model.chunk_id,
        document_id=model.document_id,
        document_version=model.document_version,
        chunk_content_hash=model.chunk_content_hash,
        model_name=model.model_name,
        model_version=model.model_version,
        configuration_fingerprint=model.configuration_fingerprint,
        dimension=model.dimension,
        normalized=model.normalized,
        status=model.status,
        processing_duration=model.processing_duration,
        retry_count=model.retry_count,
        error=model.error,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyEmbeddingRepository(EmbeddingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(self, job: EmbeddingJob) -> EmbeddingJob:
        model = EmbeddingJobModel(
            id=job.id,
            document_id=job.document_id,
            document_version=job.document_version,
            configuration_fingerprint=job.configuration_fingerprint,
            model_name=job.model_name,
            model_version=job.model_version,
            status=job.status,
            total_chunks=job.total_chunks,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _job_entity(model)

    async def get_job(self, job_id: UUID) -> EmbeddingJob | None:
        model = await self._session.get(EmbeddingJobModel, job_id)
        return _job_entity(model) if model else None

    async def latest_job(self, document_id: UUID) -> EmbeddingJob | None:
        result = await self._session.execute(
            select(EmbeddingJobModel)
            .where(EmbeddingJobModel.document_id == document_id)
            .order_by(EmbeddingJobModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _job_entity(model) if model else None

    async def update_job(self, job: EmbeddingJob) -> EmbeddingJob:
        model = await self._session.get(EmbeddingJobModel, job.id)
        if model is None:
            raise ValueError("embedding job not found")
        model.status = job.status
        model.total_chunks = job.total_chunks
        model.completed_chunks = job.completed_chunks
        model.failed_chunks = job.failed_chunks
        model.retry_count = job.retry_count
        model.error = job.error
        model.processing_duration = job.processing_duration
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return _job_entity(model)

    async def get_record(
        self, chunk_id: UUID, model_name: str, model_version: str, configuration_fingerprint: str
    ) -> EmbeddingRecord | None:
        result = await self._session.execute(
            select(EmbeddingRecordModel).where(
                EmbeddingRecordModel.chunk_id == chunk_id,
                EmbeddingRecordModel.model_name == model_name,
                EmbeddingRecordModel.model_version == model_version,
                EmbeddingRecordModel.configuration_fingerprint == configuration_fingerprint,
            )
        )
        model = result.scalar_one_or_none()
        return _record_entity(model) if model else None

    async def create_record(self, record: EmbeddingRecord) -> EmbeddingRecord:
        model = EmbeddingRecordModel(
            id=record.id,
            chunk_id=record.chunk_id,
            document_id=record.document_id,
            document_version=record.document_version,
            chunk_content_hash=record.chunk_content_hash,
            model_name=record.model_name,
            model_version=record.model_version,
            configuration_fingerprint=record.configuration_fingerprint,
            dimension=record.dimension,
            normalized=record.normalized,
            status=record.status,
            processing_duration=record.processing_duration,
            retry_count=record.retry_count,
            error=record.error,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _record_entity(model)

    async def update_record(self, record: EmbeddingRecord) -> EmbeddingRecord:
        model = await self._session.get(EmbeddingRecordModel, record.id)
        if model is None:
            raise ValueError("embedding record not found")
        model.status = record.status
        model.processing_duration = record.processing_duration
        model.retry_count = record.retry_count
        model.error = record.error
        model.updated_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(model)
        return _record_entity(model)

    async def list_document_records(
        self, document_id: UUID, document_version: int, configuration_fingerprint: str
    ) -> list[EmbeddingRecord]:
        result = await self._session.execute(
            select(EmbeddingRecordModel)
            .where(
                EmbeddingRecordModel.document_id == document_id,
                EmbeddingRecordModel.document_version == document_version,
                EmbeddingRecordModel.configuration_fingerprint == configuration_fingerprint,
            )
            .order_by(EmbeddingRecordModel.created_at)
        )
        return [_record_entity(model) for model in result.scalars().all()]

    async def list_records_for_chunks(
        self, chunk_ids: list[UUID], configuration_fingerprint: str
    ) -> list[EmbeddingRecord]:
        if not chunk_ids:
            return []
        result = await self._session.execute(
            select(EmbeddingRecordModel).where(
                EmbeddingRecordModel.chunk_id.in_(chunk_ids),
                EmbeddingRecordModel.configuration_fingerprint == configuration_fingerprint,
            )
        )
        return [_record_entity(model) for model in result.scalars().all()]

    async def statistics(self) -> dict[str, int]:
        result = await self._session.execute(
            select(EmbeddingRecordModel.status, func.count(EmbeddingRecordModel.id)).group_by(
                EmbeddingRecordModel.status
            )
        )
        return {status: count for status, count in result.all()}