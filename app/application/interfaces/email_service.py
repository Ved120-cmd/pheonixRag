from abc import ABC, abstractmethod


class EmailService(ABC):
    @abstractmethod
    async def send_verification_email(self, email: str, token: str) -> None: ...

    @abstractmethod
    async def send_password_reset_email(self, email: str, token: str) -> None: ...
