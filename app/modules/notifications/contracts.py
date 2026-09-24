"""Public notification creation/read contract."""

from __future__ import annotations

from typing import Any, Protocol


class NotificationWriter(Protocol):
    async def create(
        self,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        message: str,
        created_by: str | None,
        email_requested: bool = False,
    ) -> dict[str, Any]: ...


class NotificationReader(Protocol):
    async def list_for_user(self, user: dict[str, Any]) -> list[dict[str, Any]]: ...
