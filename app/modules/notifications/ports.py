"""Persistence port for notification operations."""

from __future__ import annotations

from typing import Any, Protocol


class NotificationRepository(Protocol):
    async def create(
        self,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        message: str,
        created_by: str | None,
        email_requested: bool,
    ) -> Any: ...

    async def get(self, notification_id: str) -> Any | None: ...

    async def list_all(self) -> list[Any]: ...

    async def read_ids(self, user_id: str) -> set[str]: ...

    async def mark_read(self, notification_id: str, user_id: str) -> None: ...

    async def is_captain(self, team_id: str, user_id: str) -> bool: ...
