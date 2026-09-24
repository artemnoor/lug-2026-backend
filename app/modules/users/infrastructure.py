"""SQLAlchemy user/profile adapter."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ...db.models import UserRow


class SqlAlchemyUserRepository:
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_by_id(self, user_id: str) -> UserRow | None:
        return await self.session.get(UserRow, user_id)

    async def is_phone_in_use(self, phone: str, excluding_user_id: str) -> bool:
        return bool(
            await self.session.scalar(
                select(UserRow.id).where(UserRow.phone == phone, UserRow.id != excluding_user_id)
            )
        )

    async def save(self, row: UserRow) -> None:
        await self.session.flush()
