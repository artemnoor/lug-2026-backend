"""User profile mutation with explicit allowlist and ownership checks."""

from __future__ import annotations

from typing import Any, Callable

from ...common.projections import user_view
from ...core.database import UnitOfWork
from ...core.errors import ConflictError, NotFoundError, ValidationAppError
from .ports import UserRepository

UserRepositoryFactory = Callable[[Any], UserRepository]


class UserService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        media: Any,
        notifications: Any,
        logger: Any,
        repository_factory: UserRepositoryFactory,
    ) -> None:
        self.uow_factory = uow_factory
        self.media = media
        self.notifications = notifications
        self.logger = logger
        self.repository_factory = repository_factory

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).get_by_id(user_id)
            return user_view(row) if row else None

    async def update_profile(self, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            row = await repository.get_by_id(user["id"])
            if row is None:
                raise NotFoundError("Пользователь не найден.", "USER_NOT_FOUND")
            allowed = {
                "fio",
                "phone",
                "messenger",
                "messenger_contact",
                "messengerContact",
                "messenger_contacts",
                "messengerContacts",
                "telegram_account",
                "telegramAccount",
                "avatar_url",
                "avatarUrl",
            }
            unknown = set(payload) - allowed - {"studentCardFile", "studentCardFileName"}
            if unknown:
                raise ValidationAppError(
                    "Некорректные поля профиля.",
                    "PROFILE_FIELDS_INVALID",
                    {"fields": sorted(unknown)},
                )
            if "fio" in payload and payload["fio"] is not None:
                row.fio = str(payload["fio"]).strip()
            phone = payload.get("phone")
            if phone is not None:
                normalized_phone = "".join(char for char in str(phone) if char.isdigit())
                if normalized_phone and await repository.is_phone_in_use(normalized_phone, row.id):
                    raise ConflictError("Этот телефон уже используется.", "PHONE_ALREADY_USED")
                row.phone = normalized_phone or None
            for source, target in (
                ("messenger", "messenger"),
                ("messengerContact", "messenger_contact"),
                ("messenger_contact", "messenger_contact"),
                ("telegramAccount", "telegram_account"),
                ("telegram_account", "telegram_account"),
                ("avatarUrl", "avatar_url"),
                ("avatar_url", "avatar_url"),
            ):
                if source in payload and payload[source] is not None:
                    setattr(row, target, str(payload[source]).strip())
            replaced = False
            new_card = str(payload.get("studentCardFile") or "").strip()
            if new_card:
                upload = await self.media.get_upload_by_url(new_card)
                if (
                    upload is None
                    or upload.get("owner_user_id") != row.id
                    or upload.get("scan_status") != "clean"
                ):
                    raise ValidationAppError(
                        "Новая фотография документа недействительна.", "UPLOAD_NOT_OWNED"
                    )
                row.student_card_file = new_card
                row.identity_status = "pending"
                replaced = True
            await repository.save(row)
            result = user_view(row)
        if replaced and self.notifications is not None:
            user_id = user["id"]
            await self.notifications.create(
                "admins",
                "",
                "identity.replaced",
                "Новое фото личного кабинета",
                f"У пользователя {user_id} новое фото личного кабинета.",
                None,
            )
        self.logger.info("profile.updated", user_id=user["id"], student_card_replaced=replaced)
        return result

    async def review_identity(
        self, user_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        status = str(payload.get("status", ""))
        comment = str(payload.get("comment") or "").strip()
        if status not in {"pending", "approved", "rejected"}:
            raise ValidationAppError(
                "Недопустимый статус проверки личности.", "IDENTITY_REVIEW_INVALID"
            )
        if status == "rejected" and not comment:
            raise ValidationAppError(
                "При отклонении обязательно укажите причину.", "REVIEW_COMMENT_REQUIRED"
            )
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            row = await repository.get_by_id(user_id)
            if row is None:
                raise NotFoundError("Пользователь не найден.", "USER_NOT_FOUND")
            row.identity_status, row.identity_comment = status, comment
            await repository.save(row)
            result = user_view(row)
        self.logger.info("identity.reviewed", actor_id=actor_id, user_id=user_id, status=status)
        return result
