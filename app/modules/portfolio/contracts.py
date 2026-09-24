"""Public portfolio contract."""

from __future__ import annotations

from typing import Any, Protocol


class PortfolioReader(Protocol):
    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]: ...

    async def score_for_team(self, team_id: str) -> float: ...


class PortfolioAdminOperations(Protocol):
    async def review_achievement(
        self, achievement_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]: ...
