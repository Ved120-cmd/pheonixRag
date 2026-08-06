"""Response schemas for the /health endpoint."""

from typing import Literal

from pydantic import BaseModel


class DependencyStatus(BaseModel):
    name: str
    status: Literal["healthy", "unhealthy"]


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    app_name: str
    app_env: str
    dependencies: list[DependencyStatus]
