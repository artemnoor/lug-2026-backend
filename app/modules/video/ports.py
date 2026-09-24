"""Video-owned persistence port."""

from __future__ import annotations

from typing import Any, Protocol


class VideoRepository(Protocol):
    async def get_team(self, team_id: str) -> Any | None: ...

    async def get_user(self, user_id: str) -> Any | None: ...

    async def get_settings(self) -> dict[str, Any]: ...

    async def update_team(self, team: Any, changes: dict[str, Any]) -> None: ...
