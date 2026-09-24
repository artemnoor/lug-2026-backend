"""Public authentication contracts used by other modules."""

from __future__ import annotations

from typing import Any, Protocol


class SessionIssuer(Protocol):
    async def issue_session(
        self, user_id: str, user_agent: str = "", ip_address: str = ""
    ) -> str: ...

    async def get_by_session(self, token_hash: str) -> dict[str, Any] | None: ...
