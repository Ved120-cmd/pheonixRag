import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_tokens: dict, registered_user: dict) -> None:
    response = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == registered_user["email"]
    assert data["username"] == registered_user["username"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_me(client: AsyncClient, auth_tokens: dict) -> None:
    response = await client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        json={"full_name": "Updated Name"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_change_password(
    client: AsyncClient, auth_tokens: dict, strong_password: str
) -> None:
    response = await client.patch(
        "/users/me/password",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
        json={"current_password": strong_password, "new_password": "NewStr0ng!Pass"},
    )
    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_me(
    client: AsyncClient, auth_tokens: dict, registered_user: dict, strong_password: str
) -> None:
    response = await client.delete(
        "/users/me",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
    )
    assert response.status_code == 200

    me = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
    )
    assert me.status_code == 401

    reregister = await client.post(
        "/auth/register",
        json={
            "email": registered_user["email"],
            "username": "newusername",
            "password": strong_password,
        },
    )
    assert reregister.status_code == 409
