from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.chunk import Chunk
from app.domain.entities.indexing import DocumentIndexState, IndexSource, IndexingJob


class IndexingRepository(ABC):
    @abstractmethod
    async def get_index_source(
        self, tenant_id: UUID, document_id: UUID, include_deleted: bool = False
    ) -> IndexSource | None:
        ...

    @abstractmethod
    async def count_index_chunks(self, tenant_id: UUID, document_id: UUID, version: int) -> int:
        ...

    @abstractmethod
    async def list_index_chunks(
        self, tenant_id: UUID, document_id: UUID, version: int, offset: int, limit: int
    ) -> list[Chunk]:
        ...

    @abstractmethod
    async def chunk_set_fingerprint(self, tenant_id: UUID, document_id: UUID, version: int) -> str:
        ...

    @abstractmethod
    async def create_or_get_job(self, job: IndexingJob) -> IndexingJob:
        ...

    @abstractmethod
    async def get_job(self, job_id: UUID) -> IndexingJob | None:
        ...

    @abstractmethod
    async def update_job(self, job: IndexingJob) -> IndexingJob:
        ...

    @abstractmethod
    async def cancel_job(self, tenant_id: UUID, job_id: UUID) -> IndexingJob | None:
        ...

    @abstractmethod
    async def latest_job(self, tenant_id: UUID, document_id: UUID) -> IndexingJob | None:
        ...

    @abstractmethod
    async def publish_version(self, state: DocumentIndexState, job: IndexingJob) -> DocumentIndexState:
        ...

    @abstractmethod
    async def get_document_state(self, tenant_id: UUID, document_id: UUID) -> DocumentIndexState | None:
        ...

    @abstractmethod
    async def clear_document_state(self, tenant_id: UUID, document_id: UUID) -> None:
        ...

    @abstractmethod
    async def active_versions(self, tenant_id: UUID) -> dict[UUID, tuple[int, str]]:
        ...

    @abstractmethod
    async def collection_is_active(self, collection_name: str) -> bool:
        ...

    @abstractmethod
    async def collection_has_live_jobs(self, collection_name: str) -> bool:
        ...

    @abstractmethod
    async def list_document_jobs(self, tenant_id: UUID, document_id: UUID) -> list[IndexingJob]:
        ...

    @abstractmethod
    async def statistics(self, tenant_id: UUID) -> dict[str, int]:
        ...