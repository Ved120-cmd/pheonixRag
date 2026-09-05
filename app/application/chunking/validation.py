from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities.chunk import Chunk, ChunkingConfig


@dataclass(frozen=True)
class ChunkValidation:
    valid: list[Chunk]
    warnings: list[str]
    rejected: int


def validate_chunks(chunks: list[Chunk], config: ChunkingConfig) -> ChunkValidation:
    valid: list[Chunk] = []
    warnings: list[str] = []
    seen_hashes: set[str] = set()
    for chunk in chunks:
        if not chunk.text.strip():
            warnings.append(f"empty chunk rejected: {chunk.id}")
            continue
        if chunk.content_hash in seen_hashes:
            warnings.append(f"duplicate chunk rejected: {chunk.id}")
            continue
        seen_hashes.add(chunk.content_hash)
        if chunk.character_count < config.minimum_chunk_size:
            warnings.append(f"small chunk: {chunk.id}")
        if chunk.character_count > config.maximum_chunk_size:
            warnings.append(f"large chunk: {chunk.id}")
        if config.overlap >= config.chunk_size:
            warnings.append("excessive overlap")
        if not chunk.document_id or not chunk.strategy or not chunk.configuration:
            warnings.append(f"missing metadata: {chunk.id}")
        if "\x00" in chunk.text:
            warnings.append(f"broken text: {chunk.id}")
        valid.append(chunk)
    return ChunkValidation(valid=valid, warnings=warnings, rejected=len(chunks) - len(valid))
