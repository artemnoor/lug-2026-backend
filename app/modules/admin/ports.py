"""Persistence port for the admin read/review façade."""

from __future__ import annotations

from typing import Any, Protocol


class AdminRepository(Protocol):
    async def overview_rows(self) -> dict[str, Any]: ...

    async def collection_rows(self, resource: str) -> list[Any]: ...

    async def audit_rows(self) -> list[Any]: ...

    async def broadcast_targets(self) -> tuple[list[Any], list[Any]]: ...
