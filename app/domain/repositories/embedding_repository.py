from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.embedding import EmbeddingJob, EmbeddingRecord


class EmbeddingRepository(ABC):
    @abstractmethod
    async def create_job(self, job: EmbeddingJob) -> EmbeddingJob:
        ...

    @abstractmethod
    async def get_job(self, job_id: UUID) -> EmbeddingJob | None:
        ...

    @abstractmethod
    async def latest_job(self, document_id: UUID) -> EmbeddingJob | None:
        ...

    @abstractmethod
    async def update_job(self, job: EmbeddingJob) -> EmbeddingJob:
        ...

    @abstractmethod
    async def get_record(
        self, chunk_id: UUID, model_name: str, model_version: str, configuration_fingerprint: str
    ) -> EmbeddingRecord | None:
        ...

    @abstractmethod
    async def create_record(self, record: EmbeddingRecord) -> EmbeddingRecord:
        ...

    @abstractmethod
    async def update_record(self, record: EmbeddingRecord) -> EmbeddingRecord:
        ...

    @abstractmethod
    async def list_document_records(
        self, document_id: UUID, document_version: int, configuration_fingerprint: str
    ) -> list[EmbeddingRecord]:
        ...

    @abstractmethod
    async def list_records_for_chunks(
        self, chunk_ids: list[UUID], configuration_fingerprint: str
    ) -> list[EmbeddingRecord]:
        ...

    @abstractmethod
    async def statistics(self) -> dict[str, int]:
        ...