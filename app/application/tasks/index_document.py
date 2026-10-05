from __future__ import annotations

import asyncio
from uuid import UUID

from qdrant_client import AsyncQdrantClient

from app.application.embeddings.registry import EmbeddingProviderRegistry
from app.config.settings import get_settings
from app.domain.entities.embedding import EmbeddingConfig
from app.domain.entities.indexing import VectorCollectionConfig
from app.infrastructure.embedding.sentence_transformer import SentenceTransformerEmbeddingProvider
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.vectorstore.qdrant_client import get_qdrant_client
from app.infrastructure.vectorstore.qdrant_vector_store import QdrantVectorStore

_provider_registry = EmbeddingProviderRegistry(SentenceTransformerEmbeddingProvider)


@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=30,
    retry_backoff=True,
    retry_jitter=True,
    name="index_document_vectors",
)
def index_document_task(self, job_id: str) -> str:
    try:
        return asyncio.run(_run(UUID(job_id)))
    except Exception as exc:
        retry_count = getattr(getattr(self, "request", None), "retries", 0)
        if retry_count >= getattr(self, "max_retries", 5):
            asyncio.run(_mark_exhausted(UUID(job_id), str(exc)))
            raise
        countdown = min(30 * (2**retry_count), 600)
        raise self.retry(exc=exc, countdown=countdown) from exc


def _build_service(session, qdrant_client=None):
    from app.application.services.indexing_service import IndexingService
    from app.infrastructure.database.repositories.embedding_repository import SQLAlchemyEmbeddingRepository
    from app.infrastructure.database.repositories.indexing_repository import SQLAlchemyIndexingRepository

    settings = get_settings()
    embedding_config = EmbeddingConfig(
        model_name=settings.embedding_model_name,
        model_version=settings.embedding_model_version,
        dimension=settings.embedding_dimension,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        normalize=settings.embedding_normalize,
        max_input_tokens=settings.embedding_max_input_tokens,
    )
    collection_config = VectorCollectionConfig.from_embedding_config(
        embedding_config,
        distance=settings.qdrant_distance,
        collection_prefix=settings.qdrant_collection_prefix,
        tenant_sharding=settings.qdrant_tenant_sharding,
    )
    return IndexingService(
        SQLAlchemyIndexingRepository(session),
        SQLAlchemyEmbeddingRepository(session),
        QdrantVectorStore(qdrant_client or get_qdrant_client()),
        _provider_registry,
        embedding_config,
        collection_config,
        batch_size=settings.qdrant_indexing_batch_size,
    )


async def _run(job_id: UUID) -> str:
    from app.infrastructure.database.session import engine
    from app.infrastructure.database.session import AsyncSessionLocal

    settings = get_settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        async with AsyncSessionLocal() as session:
            job = await _build_service(session, client).process_job(job_id)
            return str(job.id)
    finally:
        await client.close()
        await engine.dispose()


async def _mark_exhausted(job_id: UUID, error: str) -> None:
    from app.infrastructure.database.session import engine
    from app.infrastructure.database.session import AsyncSessionLocal

    settings = get_settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        async with AsyncSessionLocal() as session:
            await _build_service(session, client).mark_exhausted(job_id, error)
    finally:
        await client.close()
        await engine.dispose()


try:
    from celery.signals import worker_process_shutdown

    @worker_process_shutdown.connect
    def _release_embedding_model(**kwargs) -> None:
        _provider_registry.close()
except ImportError:  # pragma: no cover - local task shim has no Celery signals
    pass