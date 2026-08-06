import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_endpoints_forbidden_for_regular_user(
    client: AsyncClient, auth_tokens: dict
) -> None:
    response = await client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
    )
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_list_users(client: AsyncClient, admin_tokens: dict) -> None:
    response = await client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert response.status_code == 200
    assert "users" in response.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_change_user_role(
    client: AsyncClient, admin_tokens: dict, registered_user: dict
) -> None:
    response = await client.patch(
        f"/admin/users/{registered_user['id']}/role",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_can_deactivate_user(
    client: AsyncClient, admin_tokens: dict, registered_user: dict
) -> None:
    response = await client.patch(
        f"/admin/users/{registered_user['id']}/status",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(
    client: AsyncClient, admin_tokens: dict
) -> None:
    me = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    admin_id = me.json()["id"]

    response = await client.patch(
        f"/admin/users/{admin_id}/status",
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        json={"is_active": False},
    )
    assert response.status_code == 403
