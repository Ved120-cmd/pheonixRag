"""Qdrant client wrapper.

Phase 1: connection/health-check only. No collections, embeddings, or
vector search logic — that arrives in a later phase.
"""

from functools import lru_cache

from qdrant_client import AsyncQdrantClient

from app.config.settings import get_settings

settings = get_settings()


@lru_cache
def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.qdrant_url)


async def check_qdrant_health() -> bool:
    """Lightweight connectivity check used by the /health endpoint."""
    try:
        client = get_qdrant_client()
        await client.get_collections()
        return True
    except Exception:
        return False
