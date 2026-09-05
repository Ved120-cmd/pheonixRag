from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.chunk import Chunk


class ChunkRepository(ABC):
    @abstractmethod
    async def replace_active(self, document_id: UUID, version: int, chunks: list[Chunk]) -> None:
        ...

    @abstractmethod
    async def list_active(self, document_id: UUID, version: int | None = None) -> list[Chunk]:
        ...

    @abstractmethod
    async def get(self, chunk_id: UUID) -> Chunk | None:
        ...

    @abstractmethod
    async def delete_document(self, document_id: UUID) -> int:
        ...
