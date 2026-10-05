from __future__ import annotations

import logging
import math
import time
import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.application.embeddings.registry import EmbeddingProviderRegistry
from app.application.embeddings.validation import validate_embedding_batch
from app.application.interfaces.vector_store import VectorStore
from app.domain.entities.embedding import EmbeddingConfig
from app.domain.entities.chunk import Chunk
from app.domain.entities.indexing import (
    DocumentIndexState,
    IndexingJob,
    VectorCollectionConfig,
    VectorPoint,
)
from app.domain.repositories.embedding_repository import EmbeddingRepository
from app.domain.repositories.indexing_repository import IndexingRepository

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(
        self,
        indexing_repo: IndexingRepository,
        embedding_repo: EmbeddingRepository,
        vector_store: VectorStore,
        provider_registry: EmbeddingProviderRegistry,
        embedding_config: EmbeddingConfig,
        collection_config: VectorCollectionConfig,
        batch_size: int = 128,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("indexing batch size must be positive")
        self._indexing = indexing_repo
        self._embeddings = embedding_repo
        self._vectors = vector_store
        self._providers = provider_registry
        self._embedding_config = embedding_config
        self._collection_config = collection_config
        self._batch_size = batch_size

    async def create_job(
        self, tenant_id: UUID, document_id: UUID, force: bool = False
    ) -> IndexingJob:
        source = await self._indexing.get_index_source(tenant_id, document_id)
        if source is None:
            raise ValueError("document not found")
        total_chunks = await self._indexing.count_index_chunks(
            tenant_id, document_id, source.document_version
        )
        if total_chunks == 0:
            raise ValueError("document has no active chunks")
        chunk_set_fingerprint = await self._indexing.chunk_set_fingerprint(
            tenant_id, document_id, source.document_version
        )
        for offset in range(0, total_chunks, self._batch_size):
            chunks = await self._indexing.list_index_chunks(
                tenant_id, document_id, source.document_version, offset, self._batch_size
            )
            self._validate_source(source, chunks)
            records = await self._embeddings.list_records_for_chunks(
                [chunk.id for chunk in chunks], self._embedding_config.fingerprint
            )
            records_by_chunk = {record.chunk_id: record for record in records}
            for chunk in chunks:
                record = records_by_chunk.get(chunk.id)
                if (
                    record is None
                    or record.status != "completed"
                    or record.chunk_content_hash != chunk.content_hash
                    or record.dimension != self._embedding_config.dimension
                    or record.model_name != self._embedding_config.model_name
                    or record.model_version != self._embedding_config.model_version
                ):
                    raise ValueError("run embedding generation for the current document version first")
        job = await self._indexing.create_or_get_job(
            IndexingJob(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=document_id,
                document_version=source.document_version,
                chunk_set_fingerprint=chunk_set_fingerprint,
                collection_name=self._collection_config.collection_name,
                embedding_fingerprint=self._embedding_config.fingerprint,
                model_name=self._embedding_config.model_name,
                model_version=self._embedding_config.model_version,
                total_vectors=total_chunks,
            )
        )
        if force and job.status == "indexed":
            job.status = "pending"
            job.processed_vectors = 0
            job.failed_vectors = 0
            job.error = None
            job = await self._indexing.update_job(job)
        return job

    async def process_job(self, job_id: UUID) -> IndexingJob:
        job = await self._indexing.get_job(job_id)
        if job is None:
            raise ValueError("indexing job not found")
        if job.status == "indexed":
            return job
        source = await self._indexing.get_index_source(job.tenant_id, job.document_id)
        if source is None or source.document_version != job.document_version:
            job.status = "failed"
            job.error = "document is unavailable or its version has changed"
            return await self._indexing.update_job(job)
        chunk_set_fingerprint = await self._indexing.chunk_set_fingerprint(
            job.tenant_id, job.document_id, job.document_version
        )
        if chunk_set_fingerprint != job.chunk_set_fingerprint:
            job.status = "failed"
            job.error = "active chunk set changed after this indexing job was created"
            return await self._indexing.update_job(job)
        if (
            job.embedding_fingerprint != self._embedding_config.fingerprint
            or job.collection_name != self._collection_config.collection_name
            or job.model_name != self._embedding_config.model_name
            or job.model_version != self._embedding_config.model_version
        ):
            job.status = "failed"
            job.error = "indexing job configuration no longer matches the active configuration"
            return await self._indexing.update_job(job)
        total_chunks = await self._indexing.count_index_chunks(
            job.tenant_id, job.document_id, job.document_version
        )
        if total_chunks == 0:
            job.status = "failed"
            job.error = "document has no active chunks"
            return await self._indexing.update_job(job)

        previous_state = await self._indexing.get_document_state(job.tenant_id, job.document_id)
        job.status = "indexing"
        job.total_vectors = total_chunks
        job.processed_vectors = 0
        job.failed_vectors = 0
        job.error = None
        await self._indexing.update_job(job)
        started = time.perf_counter()
        try:
            collection = await self._vectors.ensure_collection(self._collection_config)
            provider = self._providers.get(self._embedding_config)
            for start in range(0, total_chunks, self._batch_size):
                current_job = await self._indexing.get_job(job.id)
                if current_job is None or current_job.status == "cancelled":
                    if not (
                        previous_state
                        and previous_state.active_collection == job.collection_name
                        and previous_state.active_document_version == job.document_version
                    ):
                        await self._vectors.delete_document(
                            job.collection_name, job.tenant_id, job.document_id, job.document_version
                        )
                    return current_job or job
                batch = await self._indexing.list_index_chunks(
                    job.tenant_id,
                    job.document_id,
                    job.document_version,
                    start,
                    self._batch_size,
                )
                if not batch:
                    raise RuntimeError("chunk page ended before the expected vector count")
                self._validate_source(source, batch)
                records = await self._embeddings.list_records_for_chunks(
                    [chunk.id for chunk in batch], self._embedding_config.fingerprint
                )
                records_by_chunk = {record.chunk_id: record for record in records}
                if any(
                    record is None
                    or record.status != "completed"
                    or record.chunk_content_hash != chunk.content_hash
                    or record.dimension != self._embedding_config.dimension
                    or record.model_name != self._embedding_config.model_name
                    or record.model_version != self._embedding_config.model_version
                    for chunk in batch
                    for record in [records_by_chunk.get(chunk.id)]
                ):
                    raise ValueError("completed Phase 6 embeddings are missing or stale")
                vectors = provider.embed([chunk.text for chunk in batch])
                validate_embedding_batch([chunk.text for chunk in batch], vectors, self._embedding_config)
                points = [
                    self._build_point(source, chunk, vector.values, job.chunk_set_fingerprint)
                    for chunk, vector in zip(batch, vectors, strict=True)
                ]
                await self._vectors.upsert_batch(collection, job.tenant_id, points)
                job.processed_vectors += len(points)
                job.updated_at = datetime.now(UTC)
                await self._indexing.update_job(job)
                logger.info(
                    "vector_index_batch_completed",
                    extra={
                        "job_id": str(job.id),
                        "tenant_id": str(job.tenant_id),
                        "document_id": str(job.document_id),
                        "batch_size": len(points),
                        "processed_vectors": job.processed_vectors,
                        "total_vectors": job.total_vectors,
                    },
                )
            current_job = await self._indexing.get_job(job.id)
            if current_job is None or current_job.status == "cancelled":
                if not (
                    previous_state
                    and previous_state.active_collection == job.collection_name
                    and previous_state.active_document_version == job.document_version
                ):
                    await self._vectors.delete_document(
                        job.collection_name, job.tenant_id, job.document_id, job.document_version
                    )
                return current_job or job
            if job.processed_vectors != job.total_vectors:
                raise RuntimeError("indexed vector count does not match expected chunk count")
            new_state = DocumentIndexState(
                tenant_id=job.tenant_id,
                document_id=job.document_id,
                active_document_version=job.document_version,
                active_chunk_set_fingerprint=job.chunk_set_fingerprint,
                active_collection=job.collection_name,
                active_embedding_fingerprint=job.embedding_fingerprint,
            )
            job.status = "indexed"
            job.duration_seconds = time.perf_counter() - started
            await self._indexing.publish_version(new_state, job)
            await self._cleanup_previous_version(previous_state, new_state)
            return job
        except Exception as exc:
            job.status = "partial" if job.processed_vectors else "failed"
            job.failed_vectors = max(0, job.total_vectors - job.processed_vectors)
            job.error = str(exc)
            job.retries += 1
            job.duration_seconds = time.perf_counter() - started
            await self._indexing.update_job(job)
            logger.exception(
                "vector_indexing_failed",
                extra={"job_id": str(job.id), "document_id": str(job.document_id)},
            )
            raise

    async def mark_exhausted(self, job_id: UUID, error: str) -> IndexingJob | None:
        job = await self._indexing.get_job(job_id)
        if job is None:
            return None
        job.status = "partial" if job.processed_vectors else "failed"
        job.failed_vectors = max(0, job.total_vectors - job.processed_vectors)
        job.error = error
        return await self._indexing.update_job(job)

    async def status(self, tenant_id: UUID, job_id: UUID) -> IndexingJob | None:
        job = await self._indexing.get_job(job_id)
        return job if job and job.tenant_id == tenant_id else None

    async def retry_job(self, tenant_id: UUID, job_id: UUID) -> IndexingJob:
        job = await self.status(tenant_id, job_id)
        if job is None:
            raise ValueError("indexing job not found")
        if job.status not in ("failed", "partial"):
            raise ValueError("only failed or partial jobs can be retried")
        source = await self._indexing.get_index_source(tenant_id, job.document_id)
        if source is None or source.document_version != job.document_version:
            raise ValueError("document changed; submit a new indexing job")
        job.status = "pending"
        job.processed_vectors = 0
        job.failed_vectors = 0
        job.error = None
        return await self._indexing.update_job(job)

    async def cancel_job(self, tenant_id: UUID, job_id: UUID) -> IndexingJob:
        job = await self._indexing.cancel_job(tenant_id, job_id)
        if job is None:
            raise ValueError("indexing job not found")
        if job.status != "cancelled":
            raise ValueError("indexing job cannot be cancelled in its current state")
        return job

    async def document_status(self, tenant_id: UUID, document_id: UUID) -> dict[str, object]:
        source = await self._indexing.get_index_source(tenant_id, document_id)
        if source is None:
            raise ValueError("document not found")
        state = await self._indexing.get_document_state(tenant_id, document_id)
        jobs = await self._indexing.list_document_jobs(tenant_id, document_id)
        return {"state": state, "latest_job": jobs[0] if jobs else None, "jobs": jobs}

    async def statistics(self, tenant_id: UUID) -> dict[str, int]:
        return await self._indexing.statistics(tenant_id)

    async def active_versions(self, tenant_id: UUID) -> dict[UUID, tuple[int, str]]:
        return await self._indexing.active_versions(tenant_id)

    async def collection_info(self) -> dict[str, object]:
        collection = await self._vectors.ensure_collection(self._collection_config)
        return await self._vectors.collection_info(collection)

    async def recreate_collection(self, confirm_data_loss: bool) -> dict[str, object]:
        collection = self._collection_config.collection_name
        if not confirm_data_loss:
            raise ValueError("explicit data-loss confirmation is required")
        if await self._indexing.collection_is_active(collection):
            raise ValueError("collection is active for indexed documents; recreate is blocked")
        if await self._indexing.collection_has_live_jobs(collection):
            raise ValueError("collection has active indexing jobs; recreate is blocked")
        try:
            await self._vectors.delete_collection(collection)
        except Exception:
            logger.exception("qdrant_collection_delete_failed", extra={"collection": collection})
            raise
        recreated = await self._vectors.ensure_collection(self._collection_config)
        return await self._vectors.collection_info(recreated)

    async def delete_document(self, tenant_id: UUID, document_id: UUID) -> dict[str, object]:
        source = await self._indexing.get_index_source(tenant_id, document_id, include_deleted=True)
        if source is None:
            raise ValueError("document not found")
        jobs = await self._indexing.list_document_jobs(tenant_id, document_id)
        collections = {job.collection_name for job in jobs}
        state = await self._indexing.get_document_state(tenant_id, document_id)
        if state and state.active_collection:
            collections.add(state.active_collection)
        latest = jobs[0] if jobs else None
        if latest:
            latest.status = "deleting"
            await self._indexing.update_job(latest)
        await self._indexing.clear_document_state(tenant_id, document_id)
        deleted = 0
        try:
            for collection_name in collections:
                deleted += await self._vectors.delete_document(
                    collection_name, tenant_id, document_id
                )
            if latest:
                latest.status = "deleted"
                latest.processed_vectors = 0
                await self._indexing.update_job(latest)
            return {"document_id": str(document_id), "status": "deleted", "delete_operations": deleted}
        except Exception as exc:
            if latest:
                latest.status = "partial" if deleted else "failed"
                latest.error = str(exc)
                await self._indexing.update_job(latest)
            raise

    async def _cleanup_previous_version(
        self, previous: DocumentIndexState | None, current: DocumentIndexState
    ) -> None:
        if previous is None or previous.active_collection is None:
            return
        if (
            previous.active_collection == current.active_collection
            and previous.active_document_version == current.active_document_version
            and previous.active_chunk_set_fingerprint == current.active_chunk_set_fingerprint
        ):
            return
        try:
            await self._vectors.delete_document(
                previous.active_collection,
                current.tenant_id,
                current.document_id,
                previous.active_document_version,
                retain_chunk_set_fingerprint=(
                    current.active_chunk_set_fingerprint
                    if previous.active_document_version == current.active_document_version
                    else None
                ),
            )
        except Exception:
            logger.exception(
                "stale_vector_cleanup_failed",
                extra={"document_id": str(current.document_id), "collection": previous.active_collection},
            )

    def _validate_source(self, source, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            if chunk.document_id != source.document_id or chunk.document_version != source.document_version:
                raise ValueError("chunk version or document does not match indexing source")
            if not isinstance(chunk.id, UUID):
                raise ValueError("chunk ID is invalid")
            if not chunk.text.strip():
                raise ValueError(f"chunk {chunk.id} is empty")

    def _build_point(
        self, source, chunk, vector: tuple[float, ...], chunk_set_fingerprint: str
    ) -> VectorPoint:
        if len(vector) != self._embedding_config.dimension:
            raise ValueError("embedding dimension does not match configured collection dimension")
        if any(not math.isfinite(value) for value in vector):
            raise ValueError("embedding vector contains non-finite values")
        point_id = deterministic_point_id(
            source.tenant_id,
            source.document_id,
            chunk.id,
            self._embedding_config.fingerprint,
            source.document_version,
            chunk_set_fingerprint,
        )
        payload = {
            "tenant_id": str(source.tenant_id),
            "user_id": str(source.tenant_id),
            "document_id": str(source.document_id),
            "document_version": source.document_version,
            "chunk_set_fingerprint": chunk_set_fingerprint,
            "chunk_id": str(chunk.id),
            "chunk_version": chunk.document_version,
            "chunk_index": chunk.chunk_index,
            "page_numbers": chunk.page_numbers,
            "section_path": chunk.section_path,
            "chunking_strategy": chunk.strategy,
            "embedding_model": self._embedding_config.model_name,
            "embedding_model_version": self._embedding_config.model_version,
            "embedding_fingerprint": self._embedding_config.fingerprint,
            "dimension": self._embedding_config.dimension,
            "content_hash": chunk.content_hash,
            "document_type": source.document_type,
            "tags": list(source.tags),
            "status": "indexed",
            "created_at": source.document_created_at.isoformat(),
        }
        return VectorPoint(point_id, vector, payload)


def deterministic_point_id(
    tenant_id: UUID,
    document_id: UUID,
    chunk_id: UUID,
    embedding_fingerprint: str,
    document_version: int = 1,
    chunk_set_fingerprint: str = "",
) -> UUID:
    identity = (
        f"{tenant_id}:{document_id}:{document_version}:{chunk_id}:"
        f"{chunk_set_fingerprint}:{embedding_fingerprint}"
    )
    return uuid.uuid5(uuid.NAMESPACE_URL, identity)