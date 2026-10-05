from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.embedding import EmbeddingConfig, EmbeddingVector


class EmbeddingProvider(Protocol):
    config: EmbeddingConfig

    def embed(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        """Embed a non-empty batch of texts."""

    def close(self) -> None:
        """Release provider resources."""