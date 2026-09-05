from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.entities.chunk import Chunk, ChunkingConfig, StructuredDocument


@dataclass(frozen=True)
class ChunkingResult:
    chunks: list[Chunk]
    statistics: dict[str, int | float]
    warnings: list[str]


class ChunkingStrategy(ABC):
    name: str

    @abstractmethod
    def chunk(self, document: StructuredDocument, config: ChunkingConfig) -> ChunkingResult:
        raise NotImplementedError

    @staticmethod
    def stats(chunks: list[Chunk], warnings: list[str] | None = None) -> ChunkingResult:
        lengths = [chunk.character_count for chunk in chunks]
        return ChunkingResult(
            chunks=chunks,
            statistics={
                "chunk_count": len(chunks),
                "total_characters": sum(lengths),
                "average_characters": sum(lengths) / len(lengths) if lengths else 0,
                "minimum_characters": min(lengths) if lengths else 0,
                "maximum_characters": max(lengths) if lengths else 0,
                "total_tokens": sum(chunk.token_count for chunk in chunks),
            },
            warnings=warnings or [],
        )
