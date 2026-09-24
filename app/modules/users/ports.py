"""Persistence port for profile operations."""

from __future__ import annotations

from typing import Any, Protocol


class UserRepository(Protocol):
    async def get_by_id(self, user_id: str) -> Any | None: ...

    async def is_phone_in_use(self, phone: str, excluding_user_id: str) -> bool: ...

    async def save(self, row: Any) -> None: ...
