"""Authorization port — RBAC today, ABAC tomorrow."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Extensible context for ABAC rules later (resource, tenant, attributes)."""

    user_id: UUID
    role_name: str
    permissions: frozenset[str]
    resource_type: str | None = None
    resource_id: str | None = None
    attributes: dict[str, Any] | None = None


class AuthorizationChecker(ABC):
    @abstractmethod
    async def has_role(self, ctx: AuthorizationContext, role_name: str) -> bool: ...

    @abstractmethod
    async def has_permission(
        self, ctx: AuthorizationContext, permission_name: str
    ) -> bool: ...
