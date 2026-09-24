"""Password reset flow with generic request response and session revocation."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, Callable

from ...common.time import now_utc
from ...core.config import EmailSettings
from ...core.database import UnitOfWork
from ...core.errors import ValidationAppError
from ...core.security import hash_password, verification_hash
from .domain import validate_new_password
from .ports import AuthRepository

AuthRepositoryFactory = Callable[[Any], AuthRepository]


class PasswordResetService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        settings: EmailSettings,
        email: Any,
        logger: Any,
        repository_factory: AuthRepositoryFactory,
    ) -> None:
        self.uow_factory = uow_factory
        self.settings = settings
        self.email = email
        self.logger = logger
        self.repository_factory = repository_factory

    async def request(self, email: str) -> None:
        from ...core.security import normalize_email, valid_email

        normalized = normalize_email(email)
        if not valid_email(normalized):
            return
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            user = await repository.get_user_by_email(normalized)
            if user is None:
                return
            previous = await repository.get_password_reset(normalized)
            code = f"{secrets.randbelow(1_000_000):06d}"
            row = previous or await repository.create_password_reset(normalized, "", now_utc())
            row.code_hash = verification_hash(self.settings.verification_secret, code, "reset")
            row.attempts = 0
            row.expires_at = now_utc() + timedelta(seconds=self.settings.verification_ttl_seconds)
            row.used_at = None
            await repository.save_password_reset(row)
        await self.email.send(
            normalized, "Восстановление доступа — ЛУГ 2026", f"Ваш код восстановления: {code}"
        )
        self.logger.info("password_reset.requested", email=normalized)

    async def reset(self, email: str, code: str, password: str) -> None:
        from ...core.security import normalize_email

        validate_new_password(password)
        normalized = normalize_email(email)
        invalid_code = False
        user = None
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            row = await repository.get_password_reset(normalized)
            if row is None:
                raise ValidationAppError("Код восстановления недействителен.", "RESET_CODE_INVALID")
            if row.expires_at < now_utc():
                raise ValidationAppError("Код восстановления истёк.", "RESET_CODE_EXPIRED")
            if row.attempts >= self.settings.verification_max_attempts:
                raise ValidationAppError(
                    "Превышено число попыток восстановления.", "RESET_CODE_ATTEMPTS_EXCEEDED"
                )
            if verification_hash(self.settings.verification_secret, code, "reset") != row.code_hash:
                await repository.increment_password_reset_attempt(normalized)
                invalid_code = True
            else:
                user = await repository.get_user_by_email(normalized)
                if user is None:
                    raise ValidationAppError(
                        "Код восстановления недействителен.", "RESET_CODE_INVALID"
                    )
                user.password_hash = await hash_password(password)
                row.used_at = now_utc()
                await repository.save_password_reset(row)
                await repository.revoke_other_sessions(user.id, "")
        if invalid_code:
            raise ValidationAppError("Код восстановления недействителен.", "RESET_CODE_INVALID")
        assert user is not None
        self.logger.info("password_reset.completed", user_id=user.id)
