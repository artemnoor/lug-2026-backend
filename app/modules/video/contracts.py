"""Public video contract."""

from __future__ import annotations

from typing import Any, Protocol


class VideoReader(Protocol):
    async def score_for_team(self, team_id: str) -> float: ...

    async def get_for_team(self, team_id: str) -> dict[str, Any] | None: ...


class VideoAdminOperations(Protocol):
    async def review_video(
        self, team_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]: ...
