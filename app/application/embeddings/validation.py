from __future__ import annotations

import math
from collections.abc import Sequence

from app.domain.entities.embedding import EmbeddingConfig, EmbeddingVector


def validate_embedding_batch(
    texts: Sequence[str], vectors: Sequence[EmbeddingVector], config: EmbeddingConfig
) -> None:
    if not texts:
        raise ValueError("embedding batch must not be empty")
    if len(texts) != len(vectors):
        raise ValueError("embedding result count does not match input count")
    for index, text in enumerate(texts):
        if not text.strip():
            raise ValueError(f"empty chunk at batch index {index}")
        vector = vectors[index]
        if vector.dimension != config.dimension:
            raise ValueError(
                f"embedding dimension mismatch: expected {config.dimension}, got {vector.dimension}"
            )
        if len(vector.values) != config.dimension:
            raise ValueError(f"embedding vector at index {index} has an invalid length")
        if not all(math.isfinite(value) for value in vector.values):
            raise ValueError(f"embedding vector at index {index} contains non-finite values")