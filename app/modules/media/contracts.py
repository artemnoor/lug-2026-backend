"""Public media contracts used by registration and participant modules."""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any, Protocol


class UploadStorage(Protocol):
    async def save_stream(
        self,
        chunks: AsyncIterable[bytes],
        name: str,
        content_type: str,
        kind: str,
        owner_subject: str,
        declared_size: int = 0,
    ) -> dict[str, Any]: ...

    async def create_intent(
        self, name: str, content_type: str, size: int, kind: str, owner_subject: str
    ) -> dict[str, Any]: ...

    async def get_intent(self, upload_id: str) -> dict[str, Any] | None: ...

    async def complete(
        self, intent: dict[str, Any], parts: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


class MediaReader(Protocol):
    async def get_upload_by_url(self, url: str) -> dict[str, Any] | None: ...

    async def can_read_upload(self, user: dict[str, Any], upload: dict[str, Any]) -> bool: ...

    async def claim_upload_for_user(self, url: str, user_id: str) -> None: ...

    def verify_registration_claim(self, token: str) -> dict[str, str] | None: ...
