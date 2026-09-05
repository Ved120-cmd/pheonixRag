from __future__ import annotations

import time
import traceback
from typing import Any

from app.application.parsers.base import ParserStrategy
from app.domain.entities.processing import new_processing_job, ProcessingJob
from app.domain.repositories.processing_repository import ProcessingRepository
from app.domain.repositories.document_repository import DocumentRepository
from app.infrastructure.storage.document_store import DocumentStore


class ProcessingService:
    def __init__(
        self,
        processing_repo: ProcessingRepository,
        document_repo: DocumentRepository,
        store: DocumentStore,
        parsers: dict[str, ParserStrategy],
    ) -> None:
        self._processing_repo = processing_repo
        self._document_repo = document_repo
        self._store = store
        self._parsers = parsers

    async def process_document(self, document_id, force: bool = False) -> ProcessingJob:
        # create job record
        job = new_processing_job(document_id)
        job = await self._processing_repo.create(job)

        doc = await self._document_repo.get_by_id(document_id)
        if not doc:
            job.status = "error"
            job.last_error = "document_not_found"
            await self._processing_repo.update(job)
            return job

        # fetch bytes
        try:
            data = await self._store.get(doc.storage_path)
        except Exception as exc:
            job.status = "failed"
            job.last_error = f"storage_error: {str(exc)}"
            job.logs = traceback.format_exc()
            await self._processing_repo.update(job)
            return job

        # choose parser
        parser = None
        if doc.mime_type and doc.mime_type in self._parsers:
            parser = self._parsers[doc.mime_type]
        else:
            # fallback to text parser if available
            parser = self._parsers.get("text")

        if parser is None:
            job.status = "failed"
            job.last_error = "no_parser_available"
            await self._processing_repo.update(job)
            return job

        # run parser
        start = time.perf_counter()
        try:
            result = parser.parse(data, doc.filename, doc.mime_type or "")
            duration = time.perf_counter() - start
            job.status = "completed"
            job.parser = parser.__class__.__name__
            job.attempt_count += 1
            job.pages = result.get("pages")
            job.char_count = result.get("char_count")
            job.word_count = result.get("word_count")
            job.processing_duration = duration
            job.extraction_quality = None
            job.structured_result = result.get("structured")
            job.logs = None
            await self._processing_repo.update(job)
            return job
        except Exception:
            job.status = "failed"
            job.attempt_count += 1
            job.last_error = "parser_exception"
            job.logs = traceback.format_exc()
            await self._processing_repo.update(job)
            return job
