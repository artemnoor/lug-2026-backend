"""Media repository port."""

from __future__ import annotations

from typing import Any, Protocol


class MediaRepository(Protocol):
    async def get_by_url(self, url: str) -> Any | None: ...

    async def save(
        self, metadata: dict[str, Any], owner_user_id: str | None, claim_subject: str | None
    ) -> Any: ...

    async def claim(self, url: str, user_id: str) -> None: ...

    async def count_for_user(self, user_id: str) -> tuple[int, int]: ...

    async def is_team_member(self, user_id: str, team_id: str) -> bool: ...

    async def is_team_shared(self, url: str, team_id: str) -> bool: ...
