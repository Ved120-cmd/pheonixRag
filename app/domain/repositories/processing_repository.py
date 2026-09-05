from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from app.domain.entities.processing import ProcessingJob


class ProcessingRepository(ABC):
    @abstractmethod
    async def create(self, job: ProcessingJob) -> ProcessingJob:
        ...

    @abstractmethod
    async def get_by_id(self, job_id: UUID) -> ProcessingJob | None:
        ...

    @abstractmethod
    async def update(self, job: ProcessingJob) -> ProcessingJob:
        ...

    @abstractmethod
    async def list_by_document(self, document_id: UUID) -> List[ProcessingJob]:
        ...
