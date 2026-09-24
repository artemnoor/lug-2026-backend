"""Pure authentication rules."""

from __future__ import annotations

import secrets

from ...core.errors import AuthenticationError, ValidationAppError
from ...core.security import normalize_email, strong_password, valid_email


def validate_login(email: str, password: str) -> str:
    normalized = normalize_email(email)
    if not valid_email(normalized) or not password:
        raise AuthenticationError("Неверный адрес электронной почты или пароль.", "AUTH_INVALID")
    return normalized


def validate_new_password(password: str) -> None:
    if not strong_password(password):
        raise ValidationAppError(
            "Пароль должен содержать минимум 8 символов, строчные и заглавные буквы, цифру и спецсимвол.",
            "PASSWORD_WEAK",
        )


def new_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
