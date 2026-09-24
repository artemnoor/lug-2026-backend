"""SQLAlchemy adapter for authentication data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, update

from ...db.models import PasswordResetRow, SessionRow, UserRow
from .ports import AuthRepository


class SqlAlchemyAuthRepository(AuthRepository):
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> UserRow | None:
        return await self.session.scalar(select(UserRow).where(UserRow.email == email))

    async def get_user_by_id(self, user_id: str) -> UserRow | None:
        return await self.session.get(UserRow, user_id)

    async def get_user_by_session(self, token_hash: str, now: datetime) -> UserRow | None:
        statement = (
            select(UserRow)
            .join(SessionRow, SessionRow.user_id == UserRow.id)
            .where(SessionRow.token_hash == token_hash, SessionRow.expires_at >= now)
        )
        return await self.session.scalar(statement)

    async def add_session(
        self, user_id: str, token_hash: str, expires_at: datetime, user_agent: str, ip_address: str
    ) -> None:
        self.session.add(
            SessionRow(
                id=token_hash[:32],
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
                user_agent=user_agent[:500],
                ip_address=ip_address[:64],
            )
        )
        await self.session.flush()

    async def list_sessions(
        self, user_id: str, current_token_hash: str, now: datetime
    ) -> list[SessionRow]:
        statement = (
            select(SessionRow)
            .where(
                SessionRow.user_id == user_id,
                SessionRow.expires_at >= now,
                SessionRow.token_hash != current_token_hash,
            )
            .order_by(SessionRow.created_at.desc())
            .limit(50)
        )
        return list((await self.session.scalars(statement)).all())

    async def revoke_session(self, token_hash: str) -> bool:
        result = await self.session.execute(
            delete(SessionRow).where(SessionRow.token_hash == token_hash)
        )
        return bool(result.rowcount)

    async def revoke_other_sessions(self, user_id: str, current_token_hash: str) -> int:
        result = await self.session.execute(
            delete(SessionRow).where(
                SessionRow.user_id == user_id, SessionRow.token_hash != current_token_hash
            )
        )
        return int(result.rowcount or 0)

    async def get_password_reset(self, email: str) -> PasswordResetRow | None:
        return await self.session.scalar(
            select(PasswordResetRow).where(
                PasswordResetRow.email == email, PasswordResetRow.used_at.is_(None)
            )
        )

    async def create_password_reset(
        self, email: str, code_hash: str, expires_at: datetime
    ) -> PasswordResetRow:
        from uuid import uuid4

        row = PasswordResetRow(
            id=str(uuid4()), email=email, code_hash=code_hash, expires_at=expires_at
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def save_password_reset(self, row: PasswordResetRow) -> None:
        await self.session.flush()

    async def increment_password_reset_attempt(self, email: str) -> None:
        await self.session.execute(
            update(PasswordResetRow)
            .where(PasswordResetRow.email == email, PasswordResetRow.used_at.is_(None))
            .values(attempts=PasswordResetRow.attempts + 1)
        )
