import re

from app.domain.exceptions import ValidationError

_MIN_LENGTH = 8
_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).+$")


def validate_password_strength(password: str) -> None:
    if len(password) < _MIN_LENGTH:
        raise ValidationError("Password must be at least 8 characters", "password")
    if not _PATTERN.match(password):
        raise ValidationError(
            "Password must include upper, lower, digit, and special character",
            "password",
        )
