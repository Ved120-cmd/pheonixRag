"""Integration tests for /health against REAL infrastructure containers.

Run only when Postgres/Redis/Qdrant/MinIO are up, e.g. via:
    docker compose up -d postgres redis qdrant minio
    pytest -m integration
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_health_endpoint_reachable(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ("healthy", "degraded")


async def test_health_reports_all_four_dependencies(client: AsyncClient) -> None:
    response = await client.get("/health")
    body = response.json()
    dep_names = {dep["name"] for dep in body["dependencies"]}
    assert dep_names == {"postgres", "redis", "qdrant", "minio"}
