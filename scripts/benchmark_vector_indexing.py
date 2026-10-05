from __future__ import annotations

import argparse
import asyncio
import sys
import time
import tracemalloc
import uuid
from pathlib import Path

from qdrant_client import AsyncQdrantClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.entities.indexing import VectorCollectionConfig, VectorPoint
from app.infrastructure.vectorstore.qdrant_vector_store import QdrantVectorStore


async def benchmark(batch_size: int, vectors_per_job: int, concurrent_jobs: int) -> None:
    client = AsyncQdrantClient(":memory:")
    store = QdrantVectorStore(client)
    tenant_ids = [uuid.uuid4() for _ in range(concurrent_jobs)]
    configs = [
        VectorCollectionConfig(
            dimension=384,
            model_name="benchmark-only",
            model_version="synthetic",
            embedding_fingerprint=f"benchmark-{batch_size}-{job_index}",
            collection_prefix="vector_benchmark",
            tenant_sharding=False,
        )
        for job_index in range(concurrent_jobs)
    ]
    collections = [await store.ensure_collection(config) for config in configs]
    tracemalloc.start()
    latencies: list[float] = []

    async def index_job(job_index: int) -> None:
        collection = collections[job_index]
        tenant_id = tenant_ids[job_index]
        document_id = uuid.uuid4()
        for start in range(0, vectors_per_job, batch_size):
            count = min(batch_size, vectors_per_job - start)
            points = [
                VectorPoint(
                    id=uuid.uuid5(uuid.NAMESPACE_URL, f"{tenant_id}:{start + offset}"),
                    vector=tuple(0.01 * (dimension + 1) for dimension in range(384)),
                    payload={
                        "tenant_id": str(tenant_id),
                        "document_id": str(document_id),
                        "document_version": 1,
                        "chunk_id": str(uuid.uuid4()),
                    },
                )
                for offset in range(count)
            ]
            started = time.perf_counter()
            await store.upsert_batch(collection, tenant_id, points)
            latencies.append(time.perf_counter() - started)

    started = time.perf_counter()
    await asyncio.gather(*(index_job(index) for index in range(concurrent_jobs)))
    duration = time.perf_counter() - started
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_vectors = vectors_per_job * concurrent_jobs
    print(
        f"batch_size={batch_size} concurrent_jobs={concurrent_jobs} vectors={total_vectors} "
        f"seconds={duration:.3f} vectors_per_second={total_vectors / duration:.2f} "
        f"mean_batch_latency_ms={sum(latencies) / len(latencies) * 1000:.2f} "
        f"peak_traced_memory_mb={peak_memory / (1024 * 1024):.2f}"
    )
    await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Qdrant vector batch throughput in local mode.")
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[32, 64, 128, 256])
    parser.add_argument("--vectors-per-job", type=int, default=1000)
    parser.add_argument("--concurrent-jobs", type=int, default=2)
    args = parser.parse_args()
    for batch_size in args.batch_sizes:
        asyncio.run(benchmark(batch_size, args.vectors_per_job, args.concurrent_jobs))


if __name__ == "__main__":
    main()