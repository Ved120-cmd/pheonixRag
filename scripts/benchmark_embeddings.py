from __future__ import annotations

import argparse
import time

from app.config.settings import get_settings
from app.domain.entities.embedding import EmbeddingConfig
from app.infrastructure.embedding.sentence_transformer import SentenceTransformerEmbeddingProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark local embedding throughput.")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--chunks", type=int, default=128)
    args = parser.parse_args()
    settings = get_settings()
    config = EmbeddingConfig(
        model_name=settings.embedding_model_name,
        model_version=settings.embedding_model_version,
        dimension=settings.embedding_dimension,
        device=settings.embedding_device,
        batch_size=args.batch_size or settings.embedding_batch_size,
        normalize=settings.embedding_normalize,
        max_input_tokens=settings.embedding_max_input_tokens,
    )
    provider = SentenceTransformerEmbeddingProvider(config)
    texts = [f"Benchmark chunk {index}. This is representative embedding input." for index in range(args.chunks)]
    started = time.perf_counter()
    for start in range(0, len(texts), config.batch_size):
        provider.embed(texts[start : start + config.batch_size])
    duration = time.perf_counter() - started
    print(f"model={config.model_name} device={config.device} batch_size={config.batch_size}")
    print(f"chunks={len(texts)} seconds={duration:.3f} chunks_per_second={len(texts) / duration:.2f}")
    provider.close()


if __name__ == "__main__":
    main()