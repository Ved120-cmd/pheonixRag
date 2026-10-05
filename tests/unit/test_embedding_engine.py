from __future__ import annotations

import uuid
from collections.abc import Sequence

import pytest

from app.application.embeddings.registry import EmbeddingProviderRegistry
from app.application.embeddings.validation import validate_embedding_batch
from app.application.services.embedding_service import EmbeddingService
from app.domain.entities.chunk import Chunk
from app.domain.entities.embedding import EmbeddingConfig, EmbeddingJob, EmbeddingRecord, EmbeddingVector
from app.infrastructure.embedding.sentence_transformer import SentenceTransformerEmbeddingProvider


def make_chunk(index: int, version: int = 1, text: str | None = None) -> Chunk:
    value = text or f"chunk {index} content"
    return Chunk(
        id=uuid.uuid4(),
        document_id=DOCUMENT_ID,
        document_version=version,
        parent_chunk_id=None,
        chunk_index=index,
        text=value,
        token_count=2,
        character_count=len(value),
        page_numbers=[],
        section_path=[],
        document_metadata={},
        strategy="recursive",
        configuration={},
        content_hash=str(index) * 64,
    )


DOCUMENT_ID = uuid.uuid4()


class FakeProvider:
    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self.calls: list[list[str]] = []
        self.fail = False

    def embed(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        self.calls.append(list(texts))
        if self.fail:
            raise RuntimeError("model failure")
        return [EmbeddingVector(tuple(float(index) for index in range(self.config.dimension)), self.config.dimension) for _ in texts]

    def close(self) -> None:
        pass


class FakeChunkRepository:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    async def list_active(self, document_id, version=None):
        return [chunk for chunk in self.chunks if version is None or chunk.document_version == version]


class FakeEmbeddingRepository:
    def __init__(self) -> None:
        self.jobs: dict[uuid.UUID, EmbeddingJob] = {}
        self.records: dict[tuple[uuid.UUID, str], EmbeddingRecord] = {}

    async def create_job(self, job):
        self.jobs[job.id] = job
        return job

    async def get_job(self, job_id):
        return self.jobs.get(job_id)

    async def latest_job(self, document_id):
        jobs = [job for job in self.jobs.values() if job.document_id == document_id]
        return max(jobs, key=lambda job: job.created_at) if jobs else None

    async def update_job(self, job):
        self.jobs[job.id] = job
        return job

    async def get_record(self, chunk_id, model_name, model_version, configuration_fingerprint):
        return self.records.get((chunk_id, configuration_fingerprint))

    async def create_record(self, record):
        self.records[(record.chunk_id, record.configuration_fingerprint)] = record
        return record

    async def update_record(self, record):
        self.records[(record.chunk_id, record.configuration_fingerprint)] = record
        return record

    async def list_document_records(self, document_id, document_version, configuration_fingerprint):
        return [
            record
            for record in self.records.values()
            if record.document_id == document_id
            and record.document_version == document_version
            and record.configuration_fingerprint == configuration_fingerprint
        ]

    async def statistics(self):
        result: dict[str, int] = {}
        for record in self.records.values():
            result[record.status] = result.get(record.status, 0) + 1
        return result


@pytest.mark.unit
def test_validation_rejects_wrong_dimension_and_non_finite_values():
    config = EmbeddingConfig(dimension=2)
    with pytest.raises(ValueError, match="dimension mismatch"):
        validate_embedding_batch(["text"], [EmbeddingVector((1.0,), 1)], config)
    with pytest.raises(ValueError, match="non-finite"):
        validate_embedding_batch(["text"], [EmbeddingVector((float("nan"), 1.0), 2)], config)


@pytest.mark.asyncio
async def test_service_batches_and_is_idempotent():
    config = EmbeddingConfig(dimension=2, batch_size=2)
    provider = FakeProvider(config)
    registry = EmbeddingProviderRegistry(lambda _: provider)
    chunks = [make_chunk(index) for index in range(5)]
    chunk_repo = FakeChunkRepository(chunks)
    embedding_repo = FakeEmbeddingRepository()
    service = EmbeddingService(chunk_repo, embedding_repo, registry, config)

    job = await service.create_job(DOCUMENT_ID)
    completed = await service.process_job(job.id)

    assert completed.status == "completed"
    assert completed.completed_chunks == 5
    assert [len(batch) for batch in provider.calls] == [2, 2, 1]
    assert len(embedding_repo.records) == 5

    second = await service.create_job(DOCUMENT_ID)
    assert second.id == job.id


@pytest.mark.asyncio
async def test_service_records_model_failure_and_retry_count():
    config = EmbeddingConfig(dimension=2)
    provider = FakeProvider(config)
    provider.fail = True
    service = EmbeddingService(
        FakeChunkRepository([make_chunk(0)]),
        FakeEmbeddingRepository(),
        EmbeddingProviderRegistry(lambda _: provider),
        config,
    )
    job = await service.create_job(DOCUMENT_ID)
    failed = await service.process_job(job.id)

    assert failed.status == "failed"
    assert failed.retry_count == 1
    assert failed.error == "model failure"


def test_registry_reuses_provider_and_invalidates_configuration():
    created: list[FakeProvider] = []

    def factory(config):
        provider = FakeProvider(config)
        created.append(provider)
        return provider

    registry = EmbeddingProviderRegistry(factory)
    config = EmbeddingConfig(dimension=2)
    assert registry.get(config) is registry.get(config)
    registry.invalidate(config.fingerprint)
    assert len(created) == 1
    assert registry.get(config) is not created[0]


def test_sentence_transformer_adapter_reuses_loaded_model_and_validates_dimension():
    class Model:
        max_seq_length = None

        def get_sentence_embedding_dimension(self):
            return 2

        def encode(self, texts, **kwargs):
            assert kwargs["batch_size"] == 4
            assert kwargs["normalize_embeddings"] is True
            return [[0.5, 0.5] for _ in texts]

    config = EmbeddingConfig(dimension=2, batch_size=4)
    provider = SentenceTransformerEmbeddingProvider(config, model=Model())
    vectors = provider.embed(["one", "two"])

    assert len(vectors) == 2
    assert vectors[0].values == (0.5, 0.5)

    class WrongDimensionModel(Model):
        def get_sentence_embedding_dimension(self):
            return 3

    with pytest.raises(ValueError, match="model dimension mismatch"):
        SentenceTransformerEmbeddingProvider(config, model=WrongDimensionModel())