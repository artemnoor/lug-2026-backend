"""Business-shaped team persistence ports."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class TeamRepository(Protocol):
    async def get_team(self, team_id: str) -> Any | None: ...

    async def get_team_by_group(self, group: str) -> Any | None: ...

    async def get_team_by_invite(self, code: str, now: datetime) -> Any | None: ...

    async def get_user(self, user_id: str) -> Any | None: ...

    async def get_user_by_email(self, email: str) -> Any | None: ...

    async def get_members(self, team_id: str) -> list[Any]: ...

    async def get_settings(self) -> dict[str, Any]: ...

    async def save_pending(
        self,
        values: dict[str, Any],
        code_hash: str,
        expires_at: datetime,
        verification_id: str | None = None,
    ) -> Any: ...

    async def get_pending(self, verification_id: str) -> Any | None: ...

    async def get_pending_by_email(self, email: str) -> Any | None: ...

    async def increment_pending_attempt(self, verification_id: str) -> None: ...

    async def update_pending_code(
        self, row: Any, code_hash: str, expires_at: datetime, now: datetime
    ) -> None: ...

    async def commit_pending(self, row: Any, now: datetime) -> Any: ...

    async def update_team(self, team: Any, changes: dict[str, Any]) -> None: ...

    async def save_user(self, user: Any) -> None: ...

    async def save_audit(
        self,
        actor_id: str | None,
        action: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> None: ...
