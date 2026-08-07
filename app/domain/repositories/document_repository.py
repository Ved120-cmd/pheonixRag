from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.document import Document


class DocumentRepository(Protocol):
    async def create(self, document: Document) -> Document:
        ...

    async def get_by_id(self, document_id: UUID) -> Document | None:
        ...

    async def update(self, document: Document) -> Document:
        ...

    async def delete(self, document_id: UUID) -> None:
        ...

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Document]:
        ...

    async def find_by_checksum(self, checksum: str) -> Document | None:
        ...
