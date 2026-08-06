"""Unit tests for /health — all downstream dependency checks are mocked so
these run without any live infrastructure (fast, isolated, CI-friendly).
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.unit


async def test_health_returns_200(client: AsyncClient, mocker) -> None:
    mocker.patch("app.api.v1.endpoints.health.check_database_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_redis_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_qdrant_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_minio_health", return_value=True)

    response = await client.get("/api/v1/health")

    assert response.status_code == 200


async def test_health_all_dependencies_healthy(client: AsyncClient, mocker) -> None:
    mocker.patch("app.api.v1.endpoints.health.check_database_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_redis_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_qdrant_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_minio_health", return_value=True)

    response = await client.get("/api/v1/health")
    body = response.json()

    assert body["status"] == "healthy"
    assert all(dep["status"] == "healthy" for dep in body["dependencies"])


async def test_health_degraded_when_dependency_down(client: AsyncClient, mocker) -> None:
    mocker.patch("app.api.v1.endpoints.health.check_database_health", return_value=False)
    mocker.patch("app.api.v1.endpoints.health.check_redis_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_qdrant_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_minio_health", return_value=True)

    response = await client.get("/api/v1/health")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "degraded"
    postgres_status = next(d for d in body["dependencies"] if d["name"] == "postgres")
    assert postgres_status["status"] == "unhealthy"


async def test_health_response_schema(client: AsyncClient, mocker) -> None:
    mocker.patch("app.api.v1.endpoints.health.check_database_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_redis_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_qdrant_health", return_value=True)
    mocker.patch("app.api.v1.endpoints.health.check_minio_health", return_value=True)

    response = await client.get("/api/v1/health")
    body = response.json()

    assert "status" in body
    assert "app_name" in body
    assert "app_env" in body
    assert "dependencies" in body
    assert isinstance(body["dependencies"], list)
