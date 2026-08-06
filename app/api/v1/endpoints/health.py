"""Health check endpoint.

Verifies connectivity to Postgres, Redis, and Qdrant. MinIO is checked too
since it's part of Phase 1 infrastructure. Ollama is intentionally NOT
checked here — it's container-only in Phase 1 with no app integration yet.
"""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.config.settings import get_settings
from app.infrastructure.cache.redis_client import check_redis_health
from app.infrastructure.database.session import check_database_health
from app.infrastructure.storage.minio_client import check_minio_health
from app.infrastructure.vectorstore.qdrant_client import check_qdrant_health
from app.schemas.health import DependencyStatus, HealthResponse

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    db_ok = await check_database_health()
    redis_ok = await check_redis_health()
    qdrant_ok = await check_qdrant_health()
    minio_ok = await run_in_threadpool(check_minio_health)

    dependencies = [
        DependencyStatus(name="postgres", status="healthy" if db_ok else "unhealthy"),
        DependencyStatus(name="redis", status="healthy" if redis_ok else "unhealthy"),
        DependencyStatus(name="qdrant", status="healthy" if qdrant_ok else "unhealthy"),
        DependencyStatus(name="minio", status="healthy" if minio_ok else "unhealthy"),
    ]

    overall = "healthy" if all(d.status == "healthy" for d in dependencies) else "degraded"

    return HealthResponse(
        status=overall,
        app_name=settings.app_name,
        app_env=settings.app_env,
        dependencies=dependencies,
    )
