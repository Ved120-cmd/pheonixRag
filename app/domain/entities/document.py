from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Document:
    id: uuid.UUID
    filename: str
    mime_type: str
    size: int
    pages: int | None
    owner_id: uuid.UUID | None
    version: int
    storage_path: str
    checksum: str | None
    status: str
    metadata: dict[str, Any] | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None


def new_document(
    filename: str,
    mime_type: str,
    size: int,
    owner_id: uuid.UUID | None,
    storage_path: str,
    checksum: str | None = None,
) -> Document:
    return Document(
        id=uuid.uuid4(),
        filename=filename,
        mime_type=mime_type,
        size=size,
        pages=None,
        owner_id=owner_id,
        version=1,
        storage_path=storage_path,
        checksum=checksum,
        status="pending",
        metadata=None,
    )
