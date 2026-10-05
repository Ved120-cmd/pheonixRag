from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from app.domain.entities.chunk import Chunk
from app.domain.entities.embedding import EmbeddingConfig


DistanceMetric = Literal["cosine", "dot", "euclid"]


@dataclass(frozen=True)
class VectorCollectionConfig:
    dimension: int
    model_name: str
    model_version: str
    embedding_fingerprint: str
    distance: DistanceMetric = "cosine"
    collection_prefix: str = "phoenixrag"
    tenant_sharding: bool = True

    def __post_init__(self) -> None:
        if self.dimension <= 0:
            raise ValueError("vector dimension must be positive")
        if self.distance not in ("cosine", "dot", "euclid"):
            raise ValueError("distance must be cosine, dot, or euclid")
        if not self.collection_prefix.strip():
            raise ValueError("collection prefix must not be empty")

    @classmethod
    def from_embedding_config(
        cls,
        config: EmbeddingConfig,
        distance: DistanceMetric = "cosine",
        collection_prefix: str = "phoenixrag",
        tenant_sharding: bool = True,
    ) -> VectorCollectionConfig:
        return cls(
            dimension=config.dimension,
            model_name=config.model_name,
            model_version=config.model_version,
            embedding_fingerprint=config.fingerprint,
            distance=distance,
            collection_prefix=collection_prefix,
            tenant_sharding=tenant_sharding,
        )

    @property
    def collection_name(self) -> str:
        identity = f"{self.model_name}:{self.model_version}:{self.embedding_fingerprint}:{self.distance}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        return f"{self.collection_prefix}_{digest}"


@dataclass(frozen=True)
class VectorPoint:
    id: uuid.UUID
    vector: tuple[float, ...]
    payload: dict[str, Any]


@dataclass(frozen=True)
class VectorSearchHit:
    id: uuid.UUID
    score: float
    payload: dict[str, Any]


@dataclass
class IndexingJob:
    id: uuid.UUID
    tenant_id: uuid.UUID
    document_id: uuid.UUID
    document_version: int
    chunk_set_fingerprint: str
    collection_name: str
    embedding_fingerprint: str
    model_name: str
    model_version: str
    status: str = "pending"
    total_vectors: int = 0
    processed_vectors: int = 0
    failed_vectors: int = 0
    retries: int = 0
    duration_seconds: float | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def progress_percent(self) -> float:
        if self.total_vectors == 0:
            return 100.0 if self.status == "indexed" else 0.0
        return round((self.processed_vectors + self.failed_vectors) / self.total_vectors * 100, 2)


@dataclass
class DocumentIndexState:
    tenant_id: uuid.UUID
    document_id: uuid.UUID
    active_document_version: int | None = None
    active_collection: str | None = None
    active_embedding_fingerprint: str | None = None
    active_chunk_set_fingerprint: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class IndexSource:
    tenant_id: uuid.UUID
    document_id: uuid.UUID
    document_version: int
    document_type: str | None
    tags: tuple[str, ...]
    document_created_at: datetime
    chunks: tuple[Chunk, ...] = ()
