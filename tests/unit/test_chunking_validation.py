from uuid import uuid4

import pytest

from app.application.chunking.strategies import RecursiveStrategy
from app.application.chunking.validation import validate_chunks
from app.domain.entities.chunk import ChunkingConfig, DocumentBlock, StructuredDocument


def test_large_input_is_chunked_without_empty_chunks():
    source = StructuredDocument(uuid4(), 1, (DocumentBlock("paragraph " * 10000),))
    config = ChunkingConfig(strategy="recursive", chunk_size=500, minimum_chunk_size=1, maximum_chunk_size=600)
    result = RecursiveStrategy().chunk(source, config)
    assert len(result.chunks) > 10
    assert all(chunk.text for chunk in result.chunks)
    assert result.statistics["chunk_count"] == len(result.chunks)


def test_invalid_overlap_is_rejected():
    with pytest.raises(ValueError, match="overlap"):
        ChunkingConfig(chunk_size=10, overlap=10)


def test_empty_blocks_are_ignored():
    source = StructuredDocument(uuid4(), 1, (DocumentBlock(""), DocumentBlock("valid text")))
    result = RecursiveStrategy().chunk(source, ChunkingConfig(minimum_chunk_size=1))
    assert [chunk.text for chunk in result.chunks] == ["valid text"]


def test_duplicate_chunks_are_removed_by_hash():
    source = StructuredDocument(uuid4(), 1, (DocumentBlock("same"), DocumentBlock("same")))
    config = ChunkingConfig(minimum_chunk_size=1)
    chunks = RecursiveStrategy().chunk(source, config).chunks
    validation = validate_chunks(chunks, config)
    assert len(validation.valid) == 1
    assert validation.rejected == 1
