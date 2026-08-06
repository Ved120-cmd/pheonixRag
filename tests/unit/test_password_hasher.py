import pytest

from app.infrastructure.security.argon2_hasher import Argon2PasswordHasher


@pytest.mark.unit
@pytest.mark.asyncio
async def test_argon2_hash_and_verify() -> None:
    hasher = Argon2PasswordHasher()
    hashed = await hasher.hash("Str0ng!Pass")
    assert hashed != "Str0ng!Pass"
    assert await hasher.verify("Str0ng!Pass", hashed)
    assert not await hasher.verify("WrongPass1!", hashed)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_argon2_needs_rehash_returns_bool() -> None:
    hasher = Argon2PasswordHasher()
    hashed = await hasher.hash("Str0ng!Pass")
    assert isinstance(await hasher.needs_rehash(hashed), bool)
