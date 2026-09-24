"""Upload use cases and object-level access policy."""

from __future__ import annotations

import secrets
from typing import Any, Callable

from ...common.projections import upload_view
from ...core.config import Settings
from ...core.database import UnitOfWork
from ...core.errors import AuthorizationError, RateLimitError
from ...core.security import issue_claim, verify_claim
from .contracts import UploadStorage
from .ports import MediaRepository

MediaRepositoryFactory = Callable[[Any], MediaRepository]


class MediaService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        settings: Settings,
        storage: UploadStorage,
        logger: Any,
        repository_factory: MediaRepositoryFactory,
    ) -> None:
        self.uow_factory = uow_factory
        self.settings = settings
        self.storage = storage
        self.logger = logger
        self.repository_factory = repository_factory

    def issue_registration_claim(self, subject: str, url: str = "", key: str = "") -> str:
        return issue_claim(
            self.settings.email.verification_secret,
            subject,
            url or key,
            self.settings.email.verification_ttl_seconds,
        )

    def verify_registration_claim(self, token: str) -> dict[str, str] | None:
        claim = verify_claim(token, self.settings.email.verification_secret)
        if claim is None:
            return None
        return {"subject": claim["subject"], "key": claim["key"]}

    async def registration_intent(self, payload: dict[str, Any]) -> dict[str, Any]:
        subject = secrets.token_urlsafe(24)
        metadata = await self.storage.create_intent(
            payload["name"], payload["contentType"], payload["size"], "student-card", subject
        )
        metadata["registrationToken"] = self.issue_registration_claim(subject, key=metadata["key"])
        return metadata

    async def get_upload_by_url(self, url: str) -> dict[str, Any] | None:
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).get_by_url(url)
            return upload_view(row) if row else None

    async def claim_upload_for_user(self, url: str, user_id: str) -> None:
        async with self.uow_factory() as uow:
            await self.repository_factory(uow.session).claim(url, user_id)

    async def registration_stream(self, chunks, name: str, content_type: str) -> dict[str, Any]:
        subject = secrets.token_urlsafe(24)
        metadata = await self.storage.save_stream(
            chunks, name, content_type, "student-card", subject
        )
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).save(metadata, None, subject)
            result = upload_view(row)
        result["registrationToken"] = self.issue_registration_claim(subject, result["url"])
        return result

    async def registration_complete(
        self, payload: dict[str, Any], claim: dict[str, str]
    ) -> dict[str, Any]:
        intent = await self.storage.get_intent(payload["uploadId"])
        if (
            intent is None
            or intent.get("owner_subject") != claim["subject"]
            or intent.get("key") != payload["key"]
        ):
            raise AuthorizationError(
                "Временная загрузка документа недействительна или истекла.",
                "REGISTRATION_UPLOAD_CLAIM_INVALID",
            )
        metadata = await self.storage.complete(intent, payload.get("parts", []))
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).save(metadata, None, claim["subject"])
            result = upload_view(row)
        result["registrationToken"] = self.issue_registration_claim(
            claim["subject"], result["url"], payload["key"]
        )
        return result

    async def stream_upload(
        self,
        chunks,
        user: dict[str, Any],
        name: str,
        content_type: str,
        kind: str,
        declared_size: int,
    ) -> dict[str, Any]:
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            count, total = await repository.count_for_user(user["id"])
            if (
                count >= self.settings.storage.max_uploads_per_user
                or total + declared_size > self.settings.storage.max_upload_bytes_per_user
            ):
                raise RateLimitError(
                    "Превышена квота файлов пользователя.", "UPLOAD_QUOTA_EXCEEDED"
                )
        metadata = await self.storage.save_stream(
            chunks, name, content_type, kind, user["id"], declared_size
        )
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).save(metadata, user["id"], None)
            return upload_view(row)

    async def create_intent(self, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        metadata = await self.storage.create_intent(
            payload["name"],
            payload["contentType"],
            payload["size"],
            payload.get("kind", "attachment"),
            user["id"],
        )
        return metadata

    async def complete(self, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        intent = await self.storage.get_intent(payload["uploadId"])
        if (
            intent is None
            or intent.get("owner_subject") != user["id"]
            or intent.get("key") != payload["key"]
        ):
            raise AuthorizationError("Временная загрузка недействительна.", "UPLOAD_CLAIM_INVALID")
        metadata = await self.storage.complete(intent, payload.get("parts", []))
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).save(metadata, user["id"], None)
            return upload_view(row)

    async def can_read_upload(self, user: dict[str, Any], upload: dict[str, Any]) -> bool:
        if user.get("role") == "admin" or upload.get("owner_user_id") == user.get("id"):
            return True
        team_id = user.get("team_id") or user.get("teamId")
        if not team_id:
            return False
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            return await repository.is_team_member(
                user["id"], team_id
            ) and await repository.is_team_shared(str(upload.get("url", "")), team_id)

    async def update_scan(self, url: str, status: str, reason: str = "") -> None:
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).get_by_url(url)
            if row is None:
                return
            row.scan_status = status
            row.status = (
                "clean" if status == "clean" else "rejected" if status == "rejected" else "scanning"
            )
            row.scan_reason = reason
