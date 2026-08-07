from __future__ import annotations

import hashlib
import json
from typing import BinaryIO
from uuid import UUID

from app.domain.entities.document import Document, new_document
from app.domain.repositories.document_repository import DocumentRepository
from app.infrastructure.storage.document_store import DocumentStore


class DocumentService:
    def __init__(self, repo: DocumentRepository, store: DocumentStore) -> None:
        self._repo = repo
        self._store = store

    async def register_upload(self, *, file_stream: BinaryIO, filename: str, mime_type: str, owner_id: UUID | None, size: int) -> Document:
        # compute checksum to detect duplicates (stream must be seekable)
        file_stream.seek(0)
        checksum = hashlib.sha256(file_stream.read()).hexdigest()
        file_stream.seek(0)

        existing = await self._repo.find_by_checksum(checksum)
        if existing:
            return existing

        storage_path = self._store.key_for(filename)
        doc = new_document(
            filename=filename,
            mime_type=mime_type,
            size=size,
            owner_id=owner_id,
            storage_path=storage_path,
            checksum=checksum,
        )
        created = await self._repo.create(doc)

        # store object asynchronously via background worker (Celery task enqueued by store)
        await self._store.put(file_stream, storage_path)

        # mark uploaded
        created.status = "uploaded"
        await self._repo.update(created)
        return created

    async def get(self, document_id: UUID) -> Document | None:
        return await self._repo.get_by_id(document_id)

    async def list(self, skip: int = 0, limit: int = 100) -> list[Document]:
        return await self._repo.list_all(skip=skip, limit=limit)

    async def soft_delete(self, document_id: UUID) -> None:
        await self._repo.delete(document_id)

    async def restore(self, document_id: UUID) -> None:
        doc = await self._repo.get_by_id(document_id)
        if not doc:
            return
        doc.deleted_at = None
        doc.status = "uploaded"
        await self._repo.update(doc)
