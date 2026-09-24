"""Persistence port for settings and public results."""

from __future__ import annotations

from typing import Any, Protocol


class ContentRepository(Protocol):
    async def get_settings(self) -> dict[str, Any]: ...

    async def ensure_settings(self, data: dict[str, Any]) -> None: ...

    async def save_settings(self, data: dict[str, Any]) -> None: ...

    async def get_result_rows(self) -> tuple[list[Any], list[Any], list[Any]]: ...
