from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from app.application.chunking.strategies import get_strategy
from app.application.chunking.validation import validate_chunks
from app.domain.entities.chunk import ChunkingConfig, StructuredDocument
from app.domain.entities.chunking_run import ChunkingRun
from app.infrastructure.database.repositories.chunk_repository import SQLAlchemyChunkRepository
from app.infrastructure.database.repositories.chunking_run_repository import SQLAlchemyChunkingRunRepository
from app.infrastructure.database.repositories.document_repository import SQLAlchemyDocumentRepository
from app.infrastructure.database.repositories.processing_repository import SQLAlchemyProcessingRepository

logger = logging.getLogger(__name__)


class ChunkingService:
    def __init__(
        self,
        chunk_repo: SQLAlchemyChunkRepository,
        run_repo: SQLAlchemyChunkingRunRepository,
        document_repo: SQLAlchemyDocumentRepository,
        processing_repo: SQLAlchemyProcessingRepository,
    ) -> None:
        self._chunks = chunk_repo
        self._runs = run_repo
        self._documents = document_repo
        self._processing = processing_repo

    async def run(self, document_id: UUID, config: ChunkingConfig, force: bool = False) -> ChunkingRun:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise ValueError("document not found")
        previous = await self._runs.latest(document_id)
        if previous and not force and previous.status == "completed" and previous.configuration == config.as_dict():
            return previous
        jobs = await self._processing.list_by_document(document_id)
        if not jobs:
            raise ValueError("document has no extracted processing result")
        latest = jobs[0]
        structured = latest.structured_result or {"text": ""}
        structured_document = StructuredDocument.from_result(document_id, document.version, structured)
        run = await self._runs.create(ChunkingRun.create(document_id, document.version, config.as_dict()))
        run.status = "running"
        run.attempts += 1
        await self._runs.update(run)
        try:
            strategy = get_strategy(config.strategy)
            result = strategy.chunk(structured_document, config)
            validation = validate_chunks(result.chunks, config)
            result_chunks = validation.valid
            for index, chunk in enumerate(result_chunks):
                chunk.chunk_index = index
            run.status = "completed"
            run.statistics = {**result.statistics, "rejected": validation.rejected}
            run.warnings = result.warnings + validation.warnings
            await self._chunks.replace_active(document_id, document.version, result_chunks)
            logger.info("chunking_completed", extra={"document_id": str(document_id), "chunks": len(result_chunks)})
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)
            logger.exception("chunking_failed", extra={"document_id": str(document_id)})
        return await self._runs.update(run)

    async def status(self, document_id: UUID) -> ChunkingRun | None:
        return await self._runs.latest(document_id)

    async def list_chunks(self, document_id: UUID, version: int | None = None):
        return await self._chunks.list_active(document_id, version)

    async def retry(self, document_id: UUID, config: ChunkingConfig) -> ChunkingRun:
        return await self.run(document_id, config, force=True)
