from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    mime_type: str
    size: int
    pages: int | None
    owner_id: UUID | None
    version: int
    storage_path: str
    checksum: str | None
    status: str
    metadata: dict | None
    created_at: datetime | None
    updated_at: datetime | None


class UploadResponse(BaseModel):
    id: UUID
    status: str


class ListDocumentsResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
