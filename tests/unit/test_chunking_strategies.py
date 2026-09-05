from uuid import uuid4

import pytest

from app.application.chunking.strategies import (
    FixedSizeStrategy,
    ParentChildStrategy,
    RecursiveStrategy,
    SemanticStrategy,
    SlidingWindowStrategy,
)
from app.application.chunking.validation import validate_chunks
from app.domain.entities.chunk import ChunkingConfig, DocumentBlock, StructuredDocument


def document(text: str = "Alpha beta gamma. Alpha beta delta.\n\nA second paragraph."):
    return StructuredDocument(uuid4(), 2, (DocumentBlock(text, 3, "Intro", ("Intro",)),), {"source": "test"})


@pytest.mark.parametrize(
    "strategy",
    [FixedSizeStrategy(), RecursiveStrategy(), SlidingWindowStrategy(), SemanticStrategy(), ParentChildStrategy()],
)
def test_each_strategy_emits_chunks(strategy):
    source = document("word " * 300)
    config = ChunkingConfig(strategy=strategy.name, chunk_size=40, overlap=5, minimum_chunk_size=1, maximum_chunk_size=500, parent_size=80, child_size=20)
    result = strategy.chunk(source, config)
    assert result.chunks
    assert all(chunk.document_id == source.document_id for chunk in result.chunks)
    assert all(chunk.token_count > 0 for chunk in result.chunks)


def test_empty_document_emits_no_chunks():
    result = RecursiveStrategy().chunk(document(""), ChunkingConfig(minimum_chunk_size=1))
    assert result.chunks == []


def test_metadata_and_parent_relationships_are_preserved():
    result = ParentChildStrategy().chunk(document("one two three four five six seven eight"), ChunkingConfig(strategy="parent_child", parent_size=20, child_size=3, minimum_chunk_size=1, maximum_chunk_size=100))
    parents = {chunk.id for chunk in result.chunks if chunk.parent_chunk_id is None}
    children = [chunk for chunk in result.chunks if chunk.parent_chunk_id is not None]
    assert parents
    assert children
    assert all(child.parent_chunk_id in parents for child in children)
    assert result.chunks[0].document_metadata == {"source": "test"}


def test_duplicate_validation_rejects_duplicate_content():
    config = ChunkingConfig(minimum_chunk_size=1)
    result = RecursiveStrategy().chunk(document("same text"), config)
    duplicate = result.chunks + [result.chunks[0]]
    validation = validate_chunks(duplicate, config)
    assert len(validation.valid) == 1
    assert validation.rejected == 1
