from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.application.embeddings.registry import EmbeddingProviderRegistry
from app.application.embeddings.validation import validate_embedding_batch
from app.application.interfaces.embedding_provider import EmbeddingProvider
from app.domain.entities.chunk import Chunk
from app.domain.entities.embedding import EmbeddingConfig, EmbeddingJob, EmbeddingRecord
from app.domain.repositories.embedding_repository import EmbeddingRepository
from app.infrastructure.database.repositories.chunk_repository import SQLAlchemyChunkRepository


class EmbeddingService:
    def __init__(
        self,
        chunk_repo: SQLAlchemyChunkRepository,
        embedding_repo: EmbeddingRepository,
        provider_registry: EmbeddingProviderRegistry,
        config: EmbeddingConfig,
    ) -> None:
        self._chunks = chunk_repo
        self._embeddings = embedding_repo
        self._providers = provider_registry
        self._config = config

    @property
    def config(self) -> EmbeddingConfig:
        return self._config

    def update_config(self, config: EmbeddingConfig) -> None:
        old_fingerprint = self._config.fingerprint
        self._config = config
        if old_fingerprint != config.fingerprint:
            self._providers.invalidate(old_fingerprint)

    async def create_job(
        self, document_id: UUID, document_version: int | None = None, force: bool = False
    ) -> EmbeddingJob:
        chunks = await self._chunks.list_active(document_id, document_version)
        if not chunks:
            raise ValueError("document has no active chunks")
        resolved_version = document_version if document_version is not None else chunks[0].document_version
        if any(chunk.document_version != resolved_version for chunk in chunks):
            raise ValueError("active chunks contain incompatible document versions")
        if not force:
            latest = await self._embeddings.latest_job(document_id)
            if (
                latest
                and latest.document_version == resolved_version
                and latest.configuration_fingerprint == self._config.fingerprint
                and latest.status == "completed"
            ):
                return latest
        job = EmbeddingJob(
            id=uuid.uuid4(),
            document_id=document_id,
            document_version=resolved_version,
            configuration_fingerprint=self._config.fingerprint,
            model_name=self._config.model_name,
            model_version=self._config.model_version,
            total_chunks=len(chunks),
        )
        return await self._embeddings.create_job(job)

    async def process_job(self, job_id: UUID) -> EmbeddingJob:
        job = await self._embeddings.get_job(job_id)
        if job is None:
            raise ValueError("embedding job not found")
        chunks = await self._chunks.list_active(job.document_id, job.document_version)
        if not chunks:
            job.status = "failed"
            job.error = "document has no active chunks"
            return await self._embeddings.update_job(job)
        if (
            job.configuration_fingerprint != self._config.fingerprint
            or job.model_name != self._config.model_name
            or job.model_version != self._config.model_version
        ):
            job.status = "failed"
            job.error = "embedding job configuration no longer matches the active configuration"
            return await self._embeddings.update_job(job)
        job.status = "running"
        job.total_chunks = len(chunks)
        job.updated_at = datetime.now(UTC)
        await self._embeddings.update_job(job)
        started = time.perf_counter()
        provider = self._providers.get(self._config)
        try:
            for start in range(0, len(chunks), self._config.batch_size):
                batch = chunks[start : start + self._config.batch_size]
                await self._process_batch(job, batch, provider)
            job.status = "completed" if job.failed_chunks == 0 else "failed"
            if job.failed_chunks:
                job.error = f"{job.failed_chunks} chunk(s) failed"
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.retry_count += 1
        job.processing_duration = time.perf_counter() - started
        job.updated_at = datetime.now(UTC)
        return await self._embeddings.update_job(job)

    async def _process_batch(
        self, job: EmbeddingJob, chunks: list[Chunk], provider: EmbeddingProvider
    ) -> None:
        pending: list[Chunk] = []
        for chunk in chunks:
            existing = await self._embeddings.get_record(
                chunk.id,
                self._config.model_name,
                self._config.model_version,
                self._config.fingerprint,
            )
            if existing and existing.status == "completed" and existing.chunk_content_hash == chunk.content_hash:
                job.completed_chunks += 1
            else:
                pending.append(chunk)
        if pending:
            started = time.perf_counter()
            vectors = provider.embed([chunk.text for chunk in pending])
            validate_embedding_batch([chunk.text for chunk in pending], vectors, self._config)
            duration = time.perf_counter() - started
            for chunk in pending:
                record = await self._embeddings.get_record(
                    chunk.id,
                    self._config.model_name,
                    self._config.model_version,
                    self._config.fingerprint,
                )
                if record is None:
                    record = EmbeddingRecord(
                        id=uuid.uuid4(),
                        chunk_id=chunk.id,
                        document_id=chunk.document_id,
                        document_version=chunk.document_version,
                        chunk_content_hash=chunk.content_hash,
                        model_name=self._config.model_name,
                        model_version=self._config.model_version,
                        configuration_fingerprint=self._config.fingerprint,
                        dimension=self._config.dimension,
                        normalized=self._config.normalize,
                    )
                    await self._embeddings.create_record(record)
                record.status = "completed"
                record.processing_duration = duration / len(pending)
                record.error = None
                await self._embeddings.update_record(record)
                job.completed_chunks += 1
        await self._embeddings.update_job(job)

    async def status(self, job_id: UUID) -> EmbeddingJob | None:
        return await self._embeddings.get_job(job_id)

    async def document_status(self, document_id: UUID) -> dict[str, object]:
        job = await self._embeddings.latest_job(document_id)
        if job is None:
            raise ValueError("embedding job not found")
        records = await self._embeddings.list_document_records(
            document_id, job.document_version, job.configuration_fingerprint
        )
        return {
            "job": job,
            "total": len(records),
            "completed": sum(record.status == "completed" for record in records),
            "failed": sum(record.status == "failed" for record in records),
        }

    async def statistics(self) -> dict[str, int]:
        return await self._embeddings.statistics()