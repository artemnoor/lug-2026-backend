"""Public user profile contract."""

from __future__ import annotations

from typing import Any, Protocol


class UserReader(Protocol):
    async def get_by_id(self, user_id: str) -> dict[str, Any] | None: ...

    async def is_phone_in_use(self, phone: str, excluding_user_id: str) -> bool: ...


class UserAdminOperations(Protocol):
    async def review_identity(
        self, user_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]: ...
