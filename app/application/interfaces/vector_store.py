from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

from app.domain.entities.indexing import VectorCollectionConfig, VectorPoint, VectorSearchHit


class VectorStore(Protocol):
    async def ensure_collection(self, config: VectorCollectionConfig) -> str: ...

    async def collection_info(self, collection_name: str) -> dict[str, object]: ...

    async def upsert_batch(
        self,
        collection_name: str,
        tenant_id: UUID,
        points: Sequence[VectorPoint],
    ) -> int: ...

    async def delete_document(
        self,
        collection_name: str,
        tenant_id: UUID,
        document_id: UUID,
        version: int | None = None,
        retain_chunk_set_fingerprint: str | None = None,
    ) -> int: ...

    async def search(
        self,
        collection_name: str,
        tenant_id: UUID,
        vector: Sequence[float],
        limit: int,
        active_document_versions: Mapping[UUID, tuple[int, str]],
        payload_filters: Mapping[str, str | int | Sequence[str] | Sequence[int]] | None = None,
    ) -> list[VectorSearchHit]: ...