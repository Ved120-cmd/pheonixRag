from app.application.interfaces.email_service import EmailService
from app.config.settings import get_settings
from app.infrastructure.logging.logger import get_logger

settings = get_settings()
logger = get_logger("phoenixrag.email")


class MockEmailService(EmailService):
    """Mock email provider — logs links instead of sending real emails."""

    async def send_verification_email(self, email: str, token: str) -> None:
        link = f"{settings.frontend_url}/verify-email?token={token}"
        logger.info(
            "mock_verification_email",
            extra={"email": email, "verification_link": link},
        )

    async def send_password_reset_email(self, email: str, token: str) -> None:
        link = f"{settings.frontend_url}/reset-password?token={token}"
        logger.info(
            "mock_password_reset_email",
            extra={"email": email, "reset_link": link},
        )
