"""SQLAlchemy achievement adapter."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import func, select

from ...db.models import AchievementRow, UserRow
from .ports import PortfolioRepository


class SqlAlchemyPortfolioRepository(PortfolioRepository):
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_user(self, user_id: str) -> UserRow | None:
        return await self.session.get(UserRow, user_id)

    async def get(self, achievement_id: str) -> AchievementRow | None:
        return await self.session.get(AchievementRow, achievement_id)

    async def list_for_user(self, user_id: str) -> list[AchievementRow]:
        return list(
            (
                await self.session.scalars(
                    select(AchievementRow)
                    .where(AchievementRow.user_id == user_id)
                    .order_by(AchievementRow.created_at.desc())
                )
            ).all()
        )

    async def list_for_team(self, team_id: str) -> list[AchievementRow]:
        return list(
            (
                await self.session.scalars(
                    select(AchievementRow).join(UserRow).where(UserRow.team_id == team_id)
                )
            ).all()
        )

    async def save(self, row: AchievementRow) -> None:
        self.session.add(row)
        await self.session.flush()

    async def create(self, values: dict[str, Any]) -> AchievementRow:
        row = AchievementRow(id=str(uuid4()), **values)
        await self.save(row)
        return row

    async def delete(self, row: AchievementRow) -> None:
        await self.session.delete(row)
        await self.session.flush()

    async def score_for_team(self, team_id: str) -> float:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(AchievementRow.points), 0))
            .join(UserRow)
            .where(UserRow.team_id == team_id, AchievementRow.status == "approved")
        )
        return float(value or 0)
