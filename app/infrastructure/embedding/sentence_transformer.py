from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.application.embeddings.validation import validate_embedding_batch
from app.domain.entities.embedding import EmbeddingConfig, EmbeddingVector


class SentenceTransformerEmbeddingProvider:
    """Sentence Transformers adapter with one model instance per provider."""

    def __init__(self, config: EmbeddingConfig, model: Any | None = None) -> None:
        self.config = config
        self._model = model or self._load_model(config)
        actual_dimension = self._model.get_sentence_embedding_dimension()
        if actual_dimension != config.dimension:
            raise ValueError(
                f"model dimension mismatch: expected {config.dimension}, got {actual_dimension}"
            )

    @staticmethod
    def _load_model(config: EmbeddingConfig) -> Any:
        from sentence_transformers import SentenceTransformer

        device = None if config.device == "auto" else config.device
        model = SentenceTransformer(config.model_name, revision=config.model_version, device=device)
        model.max_seq_length = config.max_input_tokens
        return model

    def embed(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        if not texts:
            raise ValueError("embedding batch must not be empty")
        if any(not text.strip() for text in texts):
            raise ValueError("embedding input must not contain empty text")
        encoded = self._model.encode(
            list(texts),
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors = [
            EmbeddingVector(tuple(float(value) for value in row), len(row)) for row in encoded
        ]
        validate_embedding_batch(texts, vectors, self.config)
        return vectors

    def close(self) -> None:
        self._model = None