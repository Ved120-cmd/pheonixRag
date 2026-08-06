import pytest

from app.application.interfaces.authorization_checker import AuthorizationContext
from app.infrastructure.auth.rbac_authorization_checker import RBACAuthorizationChecker


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rbac_has_role() -> None:
    checker = RBACAuthorizationChecker()
    ctx = AuthorizationContext(
        user_id=__import__("uuid").uuid4(),
        role_name="admin",
        permissions=frozenset(["admin.manage"]),
    )
    assert await checker.has_role(ctx, "admin")
    assert not await checker.has_role(ctx, "user")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rbac_has_permission() -> None:
    checker = RBACAuthorizationChecker()
    ctx = AuthorizationContext(
        user_id=__import__("uuid").uuid4(),
        role_name="user",
        permissions=frozenset(["documents.read", "chat.use"]),
    )
    assert await checker.has_permission(ctx, "documents.read")
    assert not await checker.has_permission(ctx, "admin.manage")
