"""MinIO (S3-compatible) client wrapper."""

from functools import lru_cache

from minio import Minio

from app.config.settings import get_settings

settings = get_settings()


@lru_cache
def get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
    )


def check_minio_health() -> bool:
    """Lightweight connectivity check used by the /health endpoint.

    The minio SDK is synchronous; this is called via run_in_threadpool
    from the async health endpoint to avoid blocking the event loop.
    """
    try:
        client = get_minio_client()
        client.list_buckets()
        return True
    except Exception:
        return False
