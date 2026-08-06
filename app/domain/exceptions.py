"""Domain-level exceptions — no HTTP concerns here."""

from uuid import UUID


class DomainError(Exception):
    """Base for all domain errors."""

    def __init__(self, message: str, code: str = "domain_error") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    def __init__(self, resource: str, identifier: str | UUID) -> None:
        super().__init__(f"{resource} not found: {identifier}", "not_found")


class ConflictError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, "conflict")


class AuthenticationError(DomainError):
    def __init__(self, message: str = "Invalid credentials") -> None:
        super().__init__(message, "authentication_failed")


class AuthorizationError(DomainError):
    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, "authorization_failed")


class ValidationError(DomainError):
    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message, "validation_error")


class AccountLockedError(DomainError):
    def __init__(self) -> None:
        super().__init__("Account temporarily locked", "account_locked")


class RateLimitExceededError(DomainError):
    def __init__(self) -> None:
        super().__init__("Too many requests", "rate_limit_exceeded")


class InactiveAccountError(DomainError):
    def __init__(self) -> None:
        super().__init__("Account is inactive", "inactive_account")
