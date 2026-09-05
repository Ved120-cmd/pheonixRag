from __future__ import annotations

import re
import uuid
from collections import Counter

from app.domain.entities.chunk import Chunk, ChunkingConfig, DocumentBlock, StructuredDocument
from .base import ChunkingResult, ChunkingStrategy


def _block_text(blocks: tuple[DocumentBlock, ...]) -> str:
    return "\n\n".join(block.text.strip() for block in blocks if block.text.strip())


def _metadata(blocks: tuple[DocumentBlock, ...]) -> tuple[list[int], list[str]]:
    pages = [block.page_number for block in blocks if block.page_number is not None]
    sections = [block.heading for block in blocks if block.heading]
    return pages, sections


def _windows(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    return [" ".join(words[start : start + size]) for start in range(0, len(words), step)]


class FixedSizeStrategy(ChunkingStrategy):
    name = "fixed"

    def chunk(self, document: StructuredDocument, config: ChunkingConfig) -> ChunkingResult:
        text = _block_text(document.blocks)
        pieces = _windows(text, config.chunk_size, 0)
        chunks = [Chunk.create(document, piece, i, config) for i, piece in enumerate(pieces) if piece]
        return self.stats(chunks)


class SlidingWindowStrategy(ChunkingStrategy):
    name = "sliding_window"

    def chunk(self, document: StructuredDocument, config: ChunkingConfig) -> ChunkingResult:
        text = _block_text(document.blocks)
        pieces = _windows(text, config.chunk_size, config.overlap)
        chunks = [Chunk.create(document, piece, i, config) for i, piece in enumerate(pieces) if piece]
        return self.stats(chunks)


class RecursiveStrategy(ChunkingStrategy):
    name = "recursive"
    separators = ("\n\n", "\n", ". ", "; ", ", ", " ")

    def _split(self, text: str, size: int) -> list[str]:
        if len(text) <= size:
            return [text]
        for separator in self.separators:
            parts = text.split(separator)
            if len(parts) == 1:
                continue
            result: list[str] = []
            current = ""
            for part in parts:
                candidate = f"{current}{separator}{part}" if current else part
                if len(candidate) > size and current:
                    result.extend(self._split(current, size))
                    current = part
                else:
                    current = candidate
            if current:
                result.extend(self._split(current, size))
            return result
        words = text.split()
        return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]

    def chunk(self, document: StructuredDocument, config: ChunkingConfig) -> ChunkingResult:
        chunks: list[Chunk] = []
        for block in document.blocks:
            for part in self._split(block.text.strip(), config.chunk_size):
                if part.strip():
                    chunks.append(
                        Chunk.create(
                            document,
                            part,
                            len(chunks),
                            config,
                            page_numbers=[block.page_number] if block.page_number else [],
                            section_path=list(block.section_path or ((block.heading,) if block.heading else ())),
                        )
                    )
        return self.stats(chunks)


class SemanticStrategy(ChunkingStrategy):
    name = "semantic"

    @staticmethod
    def _similarity(left: str, right: str) -> float:
        left_words = set(re.findall(r"\w+", left.lower()))
        right_words = set(re.findall(r"\w+", right.lower()))
        if not left_words or not right_words:
            return 0.0
        return len(left_words & right_words) / len(left_words | right_words)

    def chunk(self, document: StructuredDocument, config: ChunkingConfig) -> ChunkingResult:
        sentences = re.split(r"(?<=[.!?])\s+", _block_text(document.blocks))
        groups: list[str] = []
        current = ""
        for sentence in (s.strip() for s in sentences if s.strip()):
            if not current:
                current = sentence
            elif self._similarity(current, sentence) >= config.similarity_threshold and len(current) + len(sentence) <= config.maximum_chunk_size:
                current = f"{current} {sentence}"
            else:
                groups.append(current)
                current = sentence
        if current:
            groups.append(current)
        chunks = [Chunk.create(document, text, i, config) for i, text in enumerate(groups)]
        return self.stats(chunks)


class ParentChildStrategy(ChunkingStrategy):
    name = "parent_child"

    def chunk(self, document: StructuredDocument, config: ChunkingConfig) -> ChunkingResult:
        parent_config = ChunkingConfig(
            strategy=self.name,
            chunk_size=config.parent_size,
            overlap=0,
            minimum_chunk_size=config.minimum_chunk_size,
            maximum_chunk_size=max(config.maximum_chunk_size, config.parent_size),
            similarity_threshold=config.similarity_threshold,
            parent_size=config.parent_size,
            child_size=config.child_size,
        )
        child_config = ChunkingConfig(
            strategy=self.name,
            chunk_size=config.child_size,
            overlap=min(config.overlap, max(0, config.child_size - 1)),
            minimum_chunk_size=config.minimum_chunk_size,
            maximum_chunk_size=config.maximum_chunk_size,
            similarity_threshold=config.similarity_threshold,
            parent_size=config.parent_size,
            child_size=config.child_size,
        )
        parents = FixedSizeStrategy().chunk(document, parent_config).chunks
        result: list[Chunk] = []
        for parent in parents:
            parent_words = parent.text.split()
            parent_doc = StructuredDocument(document.document_id, document.version, (DocumentBlock(parent.text),), document.metadata)
            parent = Chunk.create(parent_doc, parent.text, len(result), parent_config)
            result.append(parent)
            for child_index in range(0, len(parent_words), child_config.chunk_size):
                text = " ".join(parent_words[child_index : child_index + child_config.chunk_size])
                if text:
                    result.append(Chunk.create(parent_doc, text, len(result), child_config, parent.id))
        return self.stats(result)


STRATEGIES = {
    FixedSizeStrategy.name: FixedSizeStrategy,
    RecursiveStrategy.name: RecursiveStrategy,
    SlidingWindowStrategy.name: SlidingWindowStrategy,
    SemanticStrategy.name: SemanticStrategy,
    ParentChildStrategy.name: ParentChildStrategy,
}


def get_strategy(name: str) -> ChunkingStrategy:
    try:
        return STRATEGIES[name]()
    except KeyError as exc:
        raise ValueError(f"unsupported chunking strategy: {name}") from exc
