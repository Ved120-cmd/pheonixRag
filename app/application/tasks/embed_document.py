from __future__ import annotations

import asyncio
from uuid import UUID

from app.infrastructure.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="embed_document")
def embed_document_task(self, job_id: str) -> str:
    try:
        return asyncio.run(_run(UUID(job_id)))
    except Exception as exc:
        raise self.retry(exc=exc) from exc


async def _run(job_id: UUID) -> str:
    from app.application.embeddings.registry import EmbeddingProviderRegistry
    from app.application.services.embedding_service import EmbeddingService
    from app.domain.entities.embedding import EmbeddingConfig
    from app.infrastructure.database.repositories.chunk_repository import SQLAlchemyChunkRepository
    from app.infrastructure.database.repositories.embedding_repository import SQLAlchemyEmbeddingRepository
    from app.infrastructure.database.session import AsyncSessionLocal
    from app.infrastructure.embedding.sentence_transformer import SentenceTransformerEmbeddingProvider
    from app.config.settings import get_settings

    settings = get_settings()
    config = EmbeddingConfig(
        model_name=settings.embedding_model_name,
        model_version=settings.embedding_model_version,
        dimension=settings.embedding_dimension,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        normalize=settings.embedding_normalize,
        max_input_tokens=settings.embedding_max_input_tokens,
    )
    async with AsyncSessionLocal() as session:
        service = EmbeddingService(
            SQLAlchemyChunkRepository(session),
            SQLAlchemyEmbeddingRepository(session),
            EmbeddingProviderRegistry(SentenceTransformerEmbeddingProvider),
            config,
        )
        job = await service.process_job(job_id)
        return str(job.id)