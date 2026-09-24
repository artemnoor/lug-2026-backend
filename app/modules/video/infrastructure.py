"""SQLAlchemy adapter for the video-owned persistence port."""

from __future__ import annotations

from typing import Any

from ...db.models import SettingRow, TeamRow, UserRow
from ..content.contracts import default_settings
from .ports import VideoRepository


class SqlAlchemyVideoRepository(VideoRepository):
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_team(self, team_id: str) -> TeamRow | None:
        return await self.session.get(TeamRow, team_id)

    async def get_user(self, user_id: str) -> UserRow | None:
        return await self.session.get(UserRow, user_id)

    async def get_settings(self) -> dict[str, Any]:
        row = await self.session.get(SettingRow, 1)
        return {**default_settings(), **(row.data if row else {})}

    async def update_team(self, team: TeamRow, changes: dict[str, Any]) -> None:
        for key, value in changes.items():
            setattr(team, key, value)
        await self.session.flush()
