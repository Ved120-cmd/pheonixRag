import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_login_refresh_logout(
    client: AsyncClient, strong_password: str
) -> None:
    register = await client.post(
        "/auth/register",
        json={
            "email": "flow@example.com",
            "username": "flowuser",
            "password": strong_password,
            "full_name": "Flow User",
        },
    )
    assert register.status_code == 201

    login = await client.post(
        "/auth/login",
        json={"identifier": "flow@example.com", "password": strong_password},
    )
    assert login.status_code == 200
    tokens = login.json()

    me = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "flow@example.com"

    refresh = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200
    new_tokens = refresh.json()

    old_refresh = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert old_refresh.status_code == 401

    logout = await client.post("/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, strong_password: str) -> None:
    payload = {
        "email": "dup@example.com",
        "username": "userone",
        "password": strong_password,
    }
    assert (await client.post("/auth/register", json=payload)).status_code == 201
    dup = await client.post(
        "/auth/register",
        json={**payload, "username": "usertwo"},
    )
    assert dup.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, registered_user: dict) -> None:
    response = await client.post(
        "/auth/login",
        json={"identifier": "user@example.com", "password": "WrongPass1!"},
    )
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forgot_password_always_succeeds(client: AsyncClient) -> None:
    response = await client.post("/auth/forgot-password", json={"email": "missing@example.com"})
    assert response.status_code == 200
