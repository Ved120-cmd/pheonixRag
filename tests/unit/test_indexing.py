from __future__ import annotations

import uuid
import hashlib
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from qdrant_client import AsyncQdrantClient

from app.application.embeddings.registry import EmbeddingProviderRegistry
from app.application.services.indexing_service import IndexingService, deterministic_point_id
from app.domain.entities.chunk import Chunk
from app.domain.entities.embedding import EmbeddingConfig, EmbeddingRecord, EmbeddingVector
from app.domain.entities.indexing import (
    DocumentIndexState,
    IndexSource,
    IndexingJob,
    VectorCollectionConfig,
    VectorPoint,
)
from app.infrastructure.vectorstore.qdrant_vector_store import QdrantVectorStore


class FakeProvider:
    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self.fail = False
        self.fail_on_call: int | None = None
        self.dimension_delta = 0
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        self.calls.append(list(texts))
        if self.fail or len(self.calls) == self.fail_on_call:
            raise RuntimeError("mock embedding failure")
        dimension = self.config.dimension + self.dimension_delta
        return [EmbeddingVector(tuple(0.1 for _ in range(dimension)), dimension) for _ in texts]

    def close(self) -> None:
        pass


class FakeEmbeddingRepository:
    def __init__(self, records: list[EmbeddingRecord]) -> None:
        self.records = records

    async def list_document_records(self, document_id, document_version, configuration_fingerprint):
        return [
            record
            for record in self.records
            if record.document_id == document_id
            and record.document_version == document_version
            and record.configuration_fingerprint == configuration_fingerprint
        ]

    async def list_records_for_chunks(self, chunk_ids, configuration_fingerprint):
        chunk_ids = set(chunk_ids)
        return [
            record
            for record in self.records
            if record.chunk_id in chunk_ids
            and record.configuration_fingerprint == configuration_fingerprint
        ]


class FakeIndexingRepository:
    def __init__(self, source: IndexSource) -> None:
        self.source = source
        self.jobs: dict[uuid.UUID, IndexingJob] = {}
        self.job_keys: dict[tuple[uuid.UUID, uuid.UUID, int, str, str], uuid.UUID] = {}
        self.states: dict[uuid.UUID, DocumentIndexState] = {}

    async def get_index_source(self, tenant_id, document_id, include_deleted=False):
        if tenant_id != self.source.tenant_id or document_id != self.source.document_id:
            return None
        return self.source

    async def count_index_chunks(self, tenant_id, document_id, version):
        return len(self.source.chunks) if self.source.document_version == version else 0

    async def chunk_set_fingerprint(self, tenant_id, document_id, version):
        digest = hashlib.sha256()
        for chunk in self.source.chunks:
            digest.update(f"{chunk.id}:{chunk.content_hash}\n".encode("utf-8"))
        return digest.hexdigest()

    async def list_index_chunks(self, tenant_id, document_id, version, offset, limit):
        return list(self.source.chunks[offset : offset + limit])

    async def create_or_get_job(self, job):
        key = (
            job.tenant_id,
            job.document_id,
            job.document_version,
            job.chunk_set_fingerprint,
            job.embedding_fingerprint,
        )
        existing_id = self.job_keys.get(key)
        if existing_id:
            return self.jobs[existing_id]
        self.jobs[job.id] = job
        self.job_keys[key] = job.id
        return job

    async def get_job(self, job_id):
        return self.jobs.get(job_id)

    async def update_job(self, job):
        self.jobs[job.id] = job
        return job

    async def cancel_job(self, tenant_id, job_id):
        job = self.jobs.get(job_id)
        if job is None or job.tenant_id != tenant_id:
            return None
        if job.status in ("pending", "indexing", "partial"):
            job.status = "cancelled"
        return job

    async def latest_job(self, tenant_id, document_id):
        found = [job for job in self.jobs.values() if job.tenant_id == tenant_id and job.document_id == document_id]
        return found[-1] if found else None

    async def publish_version(self, state, job):
        current = await self.get_index_source(state.tenant_id, state.document_id)
        latest = await self.latest_job(state.tenant_id, state.document_id)
        if current is None or current.document_version != state.active_document_version:
            raise ValueError("document version changed")
        if (
            await self.chunk_set_fingerprint(
                state.tenant_id, state.document_id, state.active_document_version
            )
            != state.active_chunk_set_fingerprint
        ):
            raise ValueError("chunk set changed")
        if latest is None or latest.id != job.id:
            raise ValueError("superseded job")
        job.status = "indexed"
        self.jobs[job.id] = job
        self.states[state.document_id] = state
        return state

    async def get_document_state(self, tenant_id, document_id):
        state = self.states.get(document_id)
        return state if state and state.tenant_id == tenant_id else None

    async def clear_document_state(self, tenant_id, document_id):
        self.states.pop(document_id, None)

    async def active_versions(self, tenant_id):
        return {
            document_id: (state.active_document_version, state.active_chunk_set_fingerprint)
            for document_id, state in self.states.items()
            if state.tenant_id == tenant_id
            and state.active_document_version is not None
            and state.active_chunk_set_fingerprint is not None
        }

    async def collection_is_active(self, collection_name):
        return any(state.active_collection == collection_name for state in self.states.values())

    async def collection_has_live_jobs(self, collection_name):
        return any(
            job.collection_name == collection_name and job.status in ("pending", "indexing")
            for job in self.jobs.values()
        )

    async def list_document_jobs(self, tenant_id, document_id):
        return [
            job
            for job in self.jobs.values()
            if job.tenant_id == tenant_id and job.document_id == document_id
        ]

    async def statistics(self, tenant_id):
        counts: dict[str, int] = {}
        for job in self.jobs.values():
            if job.tenant_id == tenant_id:
                counts[job.status] = counts.get(job.status, 0) + 1
        return counts


class FailingVectorStore:
    def __init__(self, wrapped: QdrantVectorStore) -> None:
        self.wrapped = wrapped
        self.fail = True

    async def ensure_collection(self, config):
        return await self.wrapped.ensure_collection(config)

    async def collection_info(self, collection_name):
        return await self.wrapped.collection_info(collection_name)

    async def upsert_batch(self, collection_name, tenant_id, points):
        if self.fail:
            raise RuntimeError("mock qdrant outage")
        return await self.wrapped.upsert_batch(collection_name, tenant_id, points)

    async def delete_document(self, *args, **kwargs):
        return await self.wrapped.delete_document(*args, **kwargs)


class CancellingVectorStore:
    def __init__(self, wrapped, indexing_repo, tenant_id, job_id):
        self.wrapped = wrapped
        self.indexing_repo = indexing_repo
        self.tenant_id = tenant_id
        self.job_id = job_id
        self.cancelled = False

    async def ensure_collection(self, config):
        return await self.wrapped.ensure_collection(config)

    async def collection_info(self, collection_name):
        return await self.wrapped.collection_info(collection_name)

    async def upsert_batch(self, collection_name, tenant_id, points):
        result = await self.wrapped.upsert_batch(collection_name, tenant_id, points)
        if not self.cancelled:
            await self.indexing_repo.cancel_job(self.tenant_id, self.job_id)
            self.cancelled = True
        return result

    async def delete_document(self, *args, **kwargs):
        return await self.wrapped.delete_document(*args, **kwargs)


class NoCleanupVectorStore:
    def __init__(self, wrapped: QdrantVectorStore) -> None:
        self.wrapped = wrapped

    async def ensure_collection(self, config):
        return await self.wrapped.ensure_collection(config)

    async def collection_info(self, collection_name):
        return await self.wrapped.collection_info(collection_name)

    async def upsert_batch(self, collection_name, tenant_id, points):
        return await self.wrapped.upsert_batch(collection_name, tenant_id, points)

    async def delete_document(self, *args, **kwargs):
        return 0


@pytest.fixture
async def qdrant_store():
    client = AsyncQdrantClient(":memory:")
    yield QdrantVectorStore(client)
    await client.close()


def make_source(version: int = 1, count: int = 3) -> IndexSource:
    tenant_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
    document_id = uuid.UUID("20000000-0000-0000-0000-000000000001")
    chunks = tuple(
        Chunk(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"chunk-{version}-{index}"),
            document_id=document_id,
            document_version=version,
            parent_chunk_id=None,
            chunk_index=index,
            text=f"chunk {version}-{index}",
            token_count=2,
            character_count=12,
            page_numbers=[index + 1],
            section_path=["section", str(index)],
            document_metadata={"private_note": "must not enter Qdrant"},
            strategy="recursive",
            configuration={"chunk_size": 500},
            content_hash=f"{version}{index}" * 32,
        )
        for index in range(count)
    )
    return IndexSource(
        tenant_id=tenant_id,
        document_id=document_id,
        document_version=version,
        document_type="application/pdf",
        tags=("guide",),
        document_created_at=datetime(2026, 1, 1, tzinfo=UTC),
        chunks=chunks,
    )


def make_records(source: IndexSource, config: EmbeddingConfig) -> list[EmbeddingRecord]:
    return [
        EmbeddingRecord(
            id=uuid.uuid4(),
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_version=chunk.document_version,
            chunk_content_hash=chunk.content_hash,
            model_name=config.model_name,
            model_version=config.model_version,
            configuration_fingerprint=config.fingerprint,
            dimension=config.dimension,
            normalized=config.normalize,
            status="completed",
        )
        for chunk in source.chunks
    ]


def make_service(source, store, batch_size=2):
    embedding_config = EmbeddingConfig(dimension=3, batch_size=4)
    collection_config = VectorCollectionConfig.from_embedding_config(
        embedding_config, tenant_sharding=False, collection_prefix="test_index"
    )
    provider = FakeProvider(embedding_config)
    indexing_repo = FakeIndexingRepository(source)
    embedding_repo = FakeEmbeddingRepository(make_records(source, embedding_config))
    service = IndexingService(
        indexing_repo,
        embedding_repo,
        store,
        EmbeddingProviderRegistry(lambda _: provider),
        embedding_config,
        collection_config,
        batch_size,
    )
    return service, indexing_repo, embedding_repo, provider, embedding_config, collection_config


@pytest.mark.asyncio
async def test_qdrant_collection_batch_upsert_filtering_and_delete(qdrant_store):
    source = make_source(count=1)
    service, repo, _, _, config, collection_config = make_service(source, qdrant_store, batch_size=1)
    job = await service.create_job(source.tenant_id, source.document_id)
    completed = await service.process_job(job.id)
    assert completed.status == "indexed"

    collection = await qdrant_store.collection_info(collection_config.collection_name)
    assert collection["points_count"] == 1
    hits = await qdrant_store.search(
        collection_config.collection_name,
        source.tenant_id,
        [0.1, 0.1, 0.1],
        10,
        await service.active_versions(source.tenant_id),
        {"document_type": "application/pdf", "tags": ["guide"]},
    )
    assert len(hits) == 1
    assert hits[0].payload["chunk_id"] == str(source.chunks[0].id)
    assert "chunk_text" not in hits[0].payload
    assert "private_note" not in hits[0].payload

    other_tenant = uuid.uuid4()
    other_point = VectorPoint(
        uuid.uuid4(),
        (0.1, 0.1, 0.1),
        {"tenant_id": str(other_tenant), "document_id": str(uuid.uuid4()), "document_version": 1},
    )
    await qdrant_store.upsert_batch(collection_config.collection_name, other_tenant, [other_point])
    tenant_hits = await qdrant_store.search(
        collection_config.collection_name,
        source.tenant_id,
        [0.1, 0.1, 0.1],
        10,
        await service.active_versions(source.tenant_id),
    )
    assert len(tenant_hits) == 1
    assert await qdrant_store.delete_document(
        collection_config.collection_name, source.tenant_id, source.document_id, 1
    ) == 1
    assert (await qdrant_store.collection_info(collection_config.collection_name))["points_count"] == 1


@pytest.mark.asyncio
async def test_version_replacement_publishes_new_version_and_removes_old_vectors(qdrant_store):
    source_v1 = make_source(version=1, count=2)
    service, indexing_repo, embedding_repo, _, _, collection_config = make_service(source_v1, qdrant_store)
    job_v1 = await service.create_job(source_v1.tenant_id, source_v1.document_id)
    assert (await service.process_job(job_v1.id)).status == "indexed"

    source_v2 = make_source(version=2, count=3)
    indexing_repo.source = source_v2
    embedding_repo.records = make_records(source_v2, service._embedding_config)
    job_v2 = await service.create_job(source_v2.tenant_id, source_v2.document_id)
    assert (await service.process_job(job_v2.id)).status == "indexed"
    assert await service.active_versions(source_v2.tenant_id) == {
        source_v2.document_id: (2, await service._indexing.chunk_set_fingerprint(
            source_v2.tenant_id, source_v2.document_id, 2
        ))
    }
    assert (await qdrant_store.collection_info(collection_config.collection_name))["points_count"] == 3
    hits = await qdrant_store.search(
        collection_config.collection_name,
        source_v2.tenant_id,
        [0.1, 0.1, 0.1],
        10,
        await service.active_versions(source_v2.tenant_id),
    )
    assert len(hits) == 3
    assert all(hit.payload["document_version"] == 2 for hit in hits)


@pytest.mark.asyncio
async def test_same_version_rechunk_publishes_only_new_chunk_set(qdrant_store):
    original = make_source(version=1, count=2)
    service, indexing_repo, embedding_repo, _, _, collection_config = make_service(
        original, qdrant_store
    )
    first = await service.create_job(original.tenant_id, original.document_id)
    assert (await service.process_job(first.id)).status == "indexed"

    rechunked = replace(
        original,
        chunks=tuple(replace(chunk, content_hash="f" * 64) for chunk in original.chunks),
    )
    indexing_repo.source = rechunked
    embedding_repo.records = make_records(rechunked, service._embedding_config)
    service._vectors = NoCleanupVectorStore(qdrant_store)
    second = await service.create_job(rechunked.tenant_id, rechunked.document_id)
    assert second.id != first.id
    assert (await service.process_job(second.id)).status == "indexed"
    assert (await qdrant_store.collection_info(collection_config.collection_name))["points_count"] == 4

    hits = await qdrant_store.search(
        collection_config.collection_name,
        rechunked.tenant_id,
        [0.1, 0.1, 0.1],
        10,
        await service.active_versions(rechunked.tenant_id),
    )
    assert len(hits) == 2
    assert all(hit.payload["content_hash"] == "f" * 64 for hit in hits)


@pytest.mark.asyncio
async def test_failed_qdrant_write_keeps_previous_version_active(qdrant_store):
    source_v1 = make_source(version=1, count=1)
    service, indexing_repo, embedding_repo, _, _, _ = make_service(source_v1, qdrant_store, batch_size=1)
    first = await service.create_job(source_v1.tenant_id, source_v1.document_id)
    assert (await service.process_job(first.id)).status == "indexed"

    source_v2 = make_source(version=2, count=1)
    indexing_repo.source = source_v2
    embedding_repo.records = make_records(source_v2, service._embedding_config)
    service._vectors = FailingVectorStore(qdrant_store)
    second = await service.create_job(source_v2.tenant_id, source_v2.document_id)
    with pytest.raises(RuntimeError, match="qdrant outage"):
        await service.process_job(second.id)
    assert (await service.active_versions(source_v1.tenant_id))[source_v1.document_id][0] == 1
    failed = await service.status(source_v1.tenant_id, second.id)
    assert failed.status == "failed"
    assert failed.failed_vectors == 1


@pytest.mark.asyncio
async def test_dimension_mismatch_fails_job_without_publishing(qdrant_store):
    source = make_source(count=1)
    service, indexing_repo, _, provider, _, _ = make_service(source, qdrant_store)
    provider.dimension_delta = 1
    job = await service.create_job(source.tenant_id, source.document_id)
    with pytest.raises(ValueError, match="dimension mismatch"):
        await service.process_job(job.id)
    assert await service.active_versions(source.tenant_id) == {}
    assert (await service.status(source.tenant_id, job.id)).status == "failed"


@pytest.mark.asyncio
async def test_partial_batch_failure_is_retryable_without_publishing(qdrant_store):
    source = make_source(count=3)
    service, _, _, provider, _, collection_config = make_service(source, qdrant_store, batch_size=1)
    provider.fail_on_call = 2
    job = await service.create_job(source.tenant_id, source.document_id)
    with pytest.raises(RuntimeError, match="mock embedding failure"):
        await service.process_job(job.id)
    partial = await service.status(source.tenant_id, job.id)
    assert partial.status == "partial"
    assert partial.processed_vectors == 1
    assert partial.failed_vectors == 2
    assert await service.active_versions(source.tenant_id) == {}

    provider.fail_on_call = None
    retry = await service.retry_job(source.tenant_id, job.id)
    assert (await service.process_job(retry.id)).status == "indexed"
    assert (await qdrant_store.collection_info(collection_config.collection_name))["points_count"] == 3


@pytest.mark.asyncio
async def test_cancelled_job_stops_after_current_batch(qdrant_store):
    source = make_source(count=3)
    service, indexing_repo, _, _, _, collection_config = make_service(source, qdrant_store, batch_size=1)
    job = await service.create_job(source.tenant_id, source.document_id)
    service._vectors = CancellingVectorStore(
        qdrant_store, indexing_repo, source.tenant_id, job.id
    )
    cancelled = await service.process_job(job.id)
    assert cancelled.status == "cancelled"
    assert await service.active_versions(source.tenant_id) == {}
    assert (await qdrant_store.collection_info(collection_config.collection_name))["points_count"] == 0


@pytest.mark.asyncio
async def test_retry_after_outage_and_delete_unpublish_vectors(qdrant_store):
    source = make_source(count=1)
    service, _, _, _, _, collection_config = make_service(source, qdrant_store, batch_size=1)
    failing_store = FailingVectorStore(qdrant_store)
    service._vectors = failing_store
    job = await service.create_job(source.tenant_id, source.document_id)
    with pytest.raises(RuntimeError, match="qdrant outage"):
        await service.process_job(job.id)
    retry = await service.retry_job(source.tenant_id, job.id)
    failing_store.fail = False
    assert (await service.process_job(retry.id)).status == "indexed"
    assert await service.active_versions(source.tenant_id) == {
        source.document_id: (1, await service._indexing.chunk_set_fingerprint(
            source.tenant_id, source.document_id, 1
        ))
    }

    result = await service.delete_document(source.tenant_id, source.document_id)
    assert result["status"] == "deleted"
    assert await service.active_versions(source.tenant_id) == {}
    assert (await qdrant_store.collection_info(collection_config.collection_name))["points_count"] == 0


@pytest.mark.asyncio
async def test_same_job_reindex_is_idempotent_and_deterministic(qdrant_store):
    source = make_source(count=2)
    service, _, _, provider, _, collection_config = make_service(source, qdrant_store)
    job = await service.create_job(source.tenant_id, source.document_id)
    await service.process_job(job.id)
    first_ids = {
        deterministic_point_id(source.tenant_id, source.document_id, chunk.id, service._embedding_config.fingerprint)
        for chunk in source.chunks
    }
    forced = await service.create_job(source.tenant_id, source.document_id, force=True)
    assert forced.id == job.id
    await service.process_job(forced.id)
    assert len(provider.calls) == 2
    assert (await qdrant_store.collection_info(collection_config.collection_name))["points_count"] == 2
    assert first_ids == {
        deterministic_point_id(source.tenant_id, source.document_id, chunk.id, service._embedding_config.fingerprint)
        for chunk in source.chunks
    }


@pytest.mark.asyncio
async def test_missing_phase6_embedding_metadata_blocks_indexing(qdrant_store):
    source = make_source(count=1)
    service, _, embedding_repo, _, _, _ = make_service(source, qdrant_store)
    embedding_repo.records = []
    with pytest.raises(ValueError, match="run embedding generation"):
        await service.create_job(source.tenant_id, source.document_id)


def test_point_id_changes_with_tenant_document_chunk_or_embedding_version():
    tenant, document, chunk = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    baseline = deterministic_point_id(tenant, document, chunk, "embedding-v1")
    assert baseline == deterministic_point_id(tenant, document, chunk, "embedding-v1")
    assert baseline != deterministic_point_id(tenant, document, chunk, "embedding-v2")
    assert baseline != deterministic_point_id(uuid.uuid4(), document, chunk, "embedding-v1")
    assert baseline != deterministic_point_id(tenant, document, chunk, "embedding-v1", 2)


@pytest.mark.asyncio
async def test_collection_rejects_incompatible_dimension(qdrant_store):
    from app.domain.entities.indexing import VectorCollectionConfig

    config = VectorCollectionConfig(3, "m", "v1", "same-fingerprint", tenant_sharding=False)
    collection = await qdrant_store.ensure_collection(config)
    wrong = VectorCollectionConfig(5, "m", "v1", "same-fingerprint", tenant_sharding=False)
    with pytest.raises(ValueError, match="dimension mismatch"):
        await qdrant_store._verify_collection(collection, wrong)
