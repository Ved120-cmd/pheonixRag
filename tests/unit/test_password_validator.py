import pytest

from app.application.validators.password_validator import validate_password_strength
from app.domain.exceptions import ValidationError


@pytest.mark.unit
def test_password_validator_rejects_short_password() -> None:
    with pytest.raises(ValidationError, match="at least 8"):
        validate_password_strength("Ab1!")


@pytest.mark.unit
def test_password_validator_rejects_weak_password() -> None:
    with pytest.raises(ValidationError, match="upper, lower"):
        validate_password_strength("password123")


@pytest.mark.unit
def test_password_validator_accepts_strong_password() -> None:
    validate_password_strength("Str0ng!Pass")
