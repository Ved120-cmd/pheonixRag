from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ChunkingRun:
    id: uuid.UUID
    document_id: uuid.UUID
    document_version: int
    status: str = "queued"
    strategy: str = "recursive"
    configuration: dict[str, Any] = field(default_factory=dict)
    statistics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(cls, document_id: uuid.UUID, version: int, config: dict[str, Any]) -> ChunkingRun:
        return cls(uuid.uuid4(), document_id, version, strategy=config["strategy"], configuration=config)
