from argon2 import PasswordHasher as Argon2
from argon2.exceptions import VerifyMismatchError

from app.application.interfaces.password_hasher import PasswordHasher

_hasher = Argon2(time_cost=3, memory_cost=65536, parallelism=4)


class Argon2PasswordHasher(PasswordHasher):
    async def hash(self, password: str) -> str:
        return _hasher.hash(password)

    async def verify(self, password: str, hashed: str) -> bool:
        try:
            return _hasher.verify(hashed, password)
        except VerifyMismatchError:
            return False

    async def needs_rehash(self, hashed: str) -> bool:
        return _hasher.check_needs_rehash(hashed)
