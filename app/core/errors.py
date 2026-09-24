"""HTTP-independent application errors and one wire-format mapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppError(Exception):
    status_code: int
    code: str
    message: str
    details: Any = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


class ValidationAppError(AppError):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR", details: Any = None) -> None:
        super().__init__(422, code, message, details)


class AuthenticationError(AppError):
    def __init__(
        self, message: str = "Требуется вход в личный кабинет.", code: str = "AUTH_REQUIRED"
    ) -> None:
        super().__init__(401, code, message)


class AuthorizationError(AppError):
    def __init__(self, message: str = "Недостаточно прав.", code: str = "FORBIDDEN") -> None:
        super().__init__(403, code, message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Ресурс не найден.", code: str = "NOT_FOUND") -> None:
        super().__init__(404, code, message)


class ConflictError(AppError):
    def __init__(self, message: str, code: str = "CONFLICT", details: Any = None) -> None:
        super().__init__(409, code, message, details)


class RateLimitError(AppError):
    def __init__(
        self, message: str = "Слишком много попыток. Повторите позже.", code: str = "RATE_LIMITED"
    ) -> None:
        super().__init__(429, code, message)


class InfrastructureError(AppError):
    def __init__(
        self, message: str = "Временная ошибка инфраструктуры.", code: str = "INFRASTRUCTURE_ERROR"
    ) -> None:
        super().__init__(503, code, message)


def error_payload(error: AppError) -> dict[str, Any]:
    """Serialize typed errors without breaking the legacy frontend parser."""

    payload: dict[str, Any] = {"error": error.message, "code": error.code}
    if error.details is not None:
        payload["details"] = error.details
    return payload
