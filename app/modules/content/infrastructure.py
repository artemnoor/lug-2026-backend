"""SQLAlchemy adapter for public competition content."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ...db.models import AchievementRow, SettingRow, TeamRow, UserRow
from .contracts import default_settings
from .ports import ContentRepository


class SqlAlchemyContentRepository(ContentRepository):
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_settings(self) -> dict[str, Any]:
        row = await self.session.get(SettingRow, 1)
        return {**default_settings(), **(row.data if row else {})}

    async def ensure_settings(self, data: dict[str, Any]) -> None:
        row = await self.session.get(SettingRow, 1)
        if row is None:
            self.session.add(SettingRow(id=1, data=data))
            await self.session.flush()

    async def save_settings(self, data: dict[str, Any]) -> None:
        row = await self.session.get(SettingRow, 1)
        if row is None:
            self.session.add(SettingRow(id=1, data=data))
        else:
            row.data = data
        await self.session.flush()

    async def get_result_rows(self) -> tuple[list[Any], list[Any], list[Any]]:
        teams = list((await self.session.scalars(select(TeamRow))).all())
        users = list(
            (await self.session.scalars(select(UserRow).where(UserRow.role != "admin"))).all()
        )
        achievements = list(
            (
                await self.session.scalars(
                    select(AchievementRow).where(AchievementRow.status == "approved")
                )
            ).all()
        )
        return teams, users, achievements
