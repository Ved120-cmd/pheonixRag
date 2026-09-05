from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.infrastructure.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="chunk_document")
def chunk_document_task(self, document_id: str, configuration: dict[str, Any]) -> str:
    """Run chunking in a worker process with bounded retries."""
    try:
        return asyncio.run(_run(UUID(document_id), configuration))
    except Exception as exc:
        raise self.retry(exc=exc) from exc


async def _run(document_id: UUID, configuration: dict[str, Any]) -> str:
    from app.application.services.chunking_service import ChunkingService
    from app.domain.entities.chunk import ChunkingConfig
    from app.infrastructure.database.repositories.chunk_repository import SQLAlchemyChunkRepository
    from app.infrastructure.database.repositories.chunking_run_repository import SQLAlchemyChunkingRunRepository
    from app.infrastructure.database.repositories.document_repository import SQLAlchemyDocumentRepository
    from app.infrastructure.database.repositories.processing_repository import SQLAlchemyProcessingRepository
    from app.infrastructure.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        service = ChunkingService(
            SQLAlchemyChunkRepository(session),
            SQLAlchemyChunkingRunRepository(session),
            SQLAlchemyDocumentRepository(session),
            SQLAlchemyProcessingRepository(session),
        )
        run = await service.run(document_id, ChunkingConfig(**configuration), force=True)
        return str(run.id)
