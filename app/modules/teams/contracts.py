"""Public team contracts used by participant/admin/content modules."""

from __future__ import annotations

from typing import Any, Protocol

from .domain import check_captain, is_admitted, portfolio_open, quota, video_open

__all__ = [
    "TeamAdminOperations",
    "TeamReader",
    "check_captain",
    "is_admitted",
    "portfolio_open",
    "quota",
    "video_open",
]


class TeamReader(Protocol):
    async def get_by_id(self, team_id: str) -> dict[str, Any] | None: ...

    async def get_members(self, team_id: str) -> list[dict[str, Any]]: ...

    async def is_captain(self, team_id: str, user_id: str) -> bool: ...

    async def get_dashboard(self, user_id: str) -> dict[str, Any] | None: ...


class TeamAdminOperations(Protocol):
    async def confirm_quota(
        self, team_id: str, confirmed: bool, actor_id: str
    ) -> dict[str, Any]: ...

    async def review_team(
        self, team_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]: ...

    async def remove_member(self, team_id: str, user_id: str, actor_id: str) -> None: ...
