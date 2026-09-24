"""Authentication application operations with explicit transaction seams."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from ...common.projections import user_view
from ...common.time import now_utc
from ...core.config import SecuritySettings
from ...core.database import UnitOfWork
from ...core.errors import AuthenticationError
from ...core.security import hash_password, hash_token, new_token, verify_password
from .domain import validate_login
from .ports import AuthRepository

AuthRepositoryFactory = Callable[[Any], AuthRepository]


class AuthService:
    """Public auth service; every mutating method owns one UoW transaction."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        security: SecuritySettings,
        logger: Any,
        repository_factory: AuthRepositoryFactory,
    ) -> None:
        self.uow_factory = uow_factory
        self.security = security
        self.logger = logger
        self.repository_factory = repository_factory

    async def get_by_session(self, token_hash: str) -> dict[str, Any] | None:
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).get_user_by_session(
                token_hash, now_utc()
            )
            return user_view(row) if row else None

    async def get_user_row_by_session(self, token_hash: str) -> Any | None:
        async with self.uow_factory() as uow:
            return await self.repository_factory(uow.session).get_user_by_session(
                token_hash, now_utc()
            )

    async def authenticate(
        self, email: str, password: str, user_agent: str = "", ip_address: str = ""
    ) -> tuple[dict[str, Any], str]:
        normalized = validate_login(email, password)
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            row = await repository.get_user_by_email(normalized)
            if row is None or not row.email_verified:
                raise AuthenticationError(
                    "Неверный адрес электронной почты или пароль.", "AUTH_INVALID"
                )
            valid, needs_rehash = await verify_password(row.password_hash, password)
            if not valid:
                raise AuthenticationError(
                    "Неверный адрес электронной почты или пароль.", "AUTH_INVALID"
                )
            if needs_rehash:
                row.password_hash = await hash_password(password)
            token = new_token()
            await repository.add_session(
                row.id,
                hash_token(token),
                now_utc() + timedelta(seconds=self.security.session_ttl_seconds),
                user_agent,
                ip_address,
            )
            self.logger.info("auth.login.success", user_id=row.id)
            return user_view(row), token

    async def issue_session(self, user_id: str, user_agent: str = "", ip_address: str = "") -> str:
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            if await repository.get_user_by_id(user_id) is None:
                raise AuthenticationError()
            token = new_token()
            await repository.add_session(
                user_id,
                hash_token(token),
                now_utc() + timedelta(seconds=self.security.session_ttl_seconds),
                user_agent,
                ip_address,
            )
            return token

    async def logout(self, token: str) -> None:
        async with self.uow_factory() as uow:
            await self.repository_factory(uow.session).revoke_session(hash_token(token))

    async def list_sessions(self, user_id: str, token: str) -> list[dict[str, Any]]:
        async with self.uow_factory() as uow:
            rows = await self.repository_factory(uow.session).list_sessions(
                user_id, hash_token(token), now_utc()
            )
            return [
                {
                    "id": row.id,
                    "createdAt": row.created_at.isoformat(),
                    "expiresAt": row.expires_at.isoformat(),
                    "userAgent": row.user_agent,
                    "ipAddress": row.ip_address,
                }
                for row in rows
            ]

    async def revoke_other_sessions(self, user_id: str, token: str) -> int:
        async with self.uow_factory() as uow:
            return await self.repository_factory(uow.session).revoke_other_sessions(
                user_id, hash_token(token)
            )
