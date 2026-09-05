from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ChunkingConfig:
    strategy: str = "recursive"
    chunk_size: int = 1000
    overlap: int = 100
    minimum_chunk_size: int = 100
    maximum_chunk_size: int = 1500
    similarity_threshold: float = 0.75
    parent_size: int = 2000
    child_size: int = 500

    def __post_init__(self) -> None:
        if self.chunk_size <= 0 or self.minimum_chunk_size < 0 or self.maximum_chunk_size <= 0:
            raise ValueError("chunk sizes must be positive")
        if self.minimum_chunk_size > self.maximum_chunk_size:
            raise ValueError("minimum_chunk_size cannot exceed maximum_chunk_size")
        if self.overlap < 0 or self.overlap >= self.chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        if not 0 <= self.similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        if self.parent_size <= 0 or self.child_size <= 0:
            raise ValueError("parent_size and child_size must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
            "minimum_chunk_size": self.minimum_chunk_size,
            "maximum_chunk_size": self.maximum_chunk_size,
            "similarity_threshold": self.similarity_threshold,
            "parent_size": self.parent_size,
            "child_size": self.child_size,
        }


@dataclass(frozen=True)
class DocumentBlock:
    text: str
    page_number: int | None = None
    heading: str | None = None
    section_path: tuple[str, ...] = ()
    block_type: str = "paragraph"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StructuredDocument:
    document_id: uuid.UUID
    version: int = 1
    blocks: tuple[DocumentBlock, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_result(
        cls, document_id: uuid.UUID, version: int, result: dict[str, Any] | None
    ) -> StructuredDocument:
        result = result or {}
        raw_blocks = result.get("blocks") or []
        blocks: list[DocumentBlock] = []
        for raw in raw_blocks:
            if isinstance(raw, str):
                blocks.append(DocumentBlock(text=raw))
                continue
            if raw.get("text"):
                section = raw.get("section_path") or raw.get("heading") or ()
                if isinstance(section, str):
                    section = (section,)
                blocks.append(
                    DocumentBlock(
                        text=str(raw["text"]),
                        page_number=raw.get("page_number"),
                        heading=raw.get("heading"),
                        section_path=tuple(section),
                        block_type=raw.get("block_type", "paragraph"),
                        metadata=dict(raw.get("metadata") or {}),
                    )
                )
        if not blocks and result.get("text"):
            blocks = [DocumentBlock(text=str(result["text"]))]
        return cls(
            document_id=document_id,
            version=version,
            blocks=tuple(blocks),
            metadata=dict(result.get("metadata") or {}),
        )


@dataclass
class Chunk:
    id: uuid.UUID
    document_id: uuid.UUID
    document_version: int
    parent_chunk_id: uuid.UUID | None
    chunk_index: int
    text: str
    token_count: int
    character_count: int
    page_numbers: list[int]
    section_path: list[str]
    document_metadata: dict[str, Any]
    strategy: str
    configuration: dict[str, Any]
    content_hash: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        document: StructuredDocument,
        text: str,
        index: int,
        config: ChunkingConfig,
        parent_chunk_id: uuid.UUID | None = None,
        page_numbers: list[int] | None = None,
        section_path: list[str] | None = None,
    ) -> Chunk:
        normalized = re.sub(r"\s+", " ", text).strip()
        return cls(
            id=uuid.uuid4(),
            document_id=document.document_id,
            document_version=document.version,
            parent_chunk_id=parent_chunk_id,
            chunk_index=index,
            text=normalized,
            token_count=len(re.findall(r"\S+", normalized)),
            character_count=len(normalized),
            page_numbers=sorted(set(page_numbers or [])),
            section_path=section_path or [],
            document_metadata=dict(document.metadata),
            strategy=config.strategy,
            configuration=config.as_dict(),
            content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        )
