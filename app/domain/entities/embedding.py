from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


EmbeddingDevice = Literal["auto", "cpu", "cuda"]


@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str = "BAAI/bge-small-en-v1.5"
    model_version: str = "main"
    dimension: int = 384
    device: EmbeddingDevice = "auto"
    batch_size: int = 32
    normalize: bool = True
    max_input_tokens: int = 512

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if not self.model_version.strip():
            raise ValueError("model_version must not be empty")
        if self.dimension <= 0:
            raise ValueError("dimension must be positive")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.max_input_tokens <= 0:
            raise ValueError("max_input_tokens must be positive")
        if self.device not in ("auto", "cpu", "cuda"):
            raise ValueError("device must be auto, cpu, or cuda")

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "dimension": self.dimension,
            "device": self.device,
            "batch_size": self.batch_size,
            "normalize": self.normalize,
            "max_input_tokens": self.max_input_tokens,
        }

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EmbeddingVector:
    values: tuple[float, ...]
    dimension: int


@dataclass
class EmbeddingRecord:
    id: uuid.UUID
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version: int
    chunk_content_hash: str
    model_name: str
    model_version: str
    configuration_fingerprint: str
    dimension: int
    normalized: bool
    status: str = "queued"
    processing_duration: float | None = None
    retry_count: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class EmbeddingJob:
    id: uuid.UUID
    document_id: uuid.UUID
    document_version: int
    configuration_fingerprint: str
    model_name: str
    model_version: str
    status: str = "queued"
    total_chunks: int = 0
    completed_chunks: int = 0
    failed_chunks: int = 0
    retry_count: int = 0
    error: str | None = None
    processing_duration: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def progress_percent(self) -> float:
        if self.total_chunks == 0:
            return 100.0 if self.status == "completed" else 0.0
        return round((self.completed_chunks + self.failed_chunks) / self.total_chunks * 100, 2)