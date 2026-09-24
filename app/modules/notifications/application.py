"""Notification visibility and broadcast operations."""

from __future__ import annotations

from typing import Any, Callable

from ...common.projections import notification_view
from ...core.database import UnitOfWork
from ...core.errors import ValidationAppError
from .ports import NotificationRepository

NotificationRepositoryFactory = Callable[[Any], NotificationRepository]


class NotificationService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        email: Any,
        logger: Any,
        repository_factory: NotificationRepositoryFactory,
    ) -> None:
        self.uow_factory = uow_factory
        self.email = email
        self.logger = logger
        self.repository_factory = repository_factory

    async def create(
        self,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        message: str,
        created_by: str | None,
        email_requested: bool = False,
    ) -> dict[str, Any]:
        if target_type not in {"all", "teams", "team", "captains", "captain", "user", "admins"}:
            raise ValidationAppError(
                "Некорректная аудитория уведомления.", "NOTIFICATION_TARGET_INVALID"
            )
        if kind == "chat":
            raise ValidationAppError("Тип chat удалён из API.", "CHAT_REMOVED")
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).create(
                target_type,
                target_id,
                kind,
                title.strip(),
                message.strip(),
                created_by,
                email_requested,
            )
            result = notification_view(row)
        self.logger.info(
            "notification.created", notification_id=result["id"], target_type=target_type, kind=kind
        )
        return result

    async def list_for_user(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            rows = await repository.list_all()
            read_ids = await repository.read_ids(user["id"])
            team_id = user.get("teamId") or user.get("team_id")
            is_captain = bool(team_id and await repository.is_captain(team_id, str(user.get("id"))))
            visible = []
            for row in rows:
                if self._visible(row, user, is_captain):
                    visible.append(notification_view(row, row.id in read_ids))
            return visible

    async def mark_read(self, notification_id: str, user: dict[str, Any]) -> bool:
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            row = await repository.get(notification_id)
            team_id = user.get("teamId") or user.get("team_id")
            is_captain = bool(team_id and await repository.is_captain(team_id, str(user.get("id"))))
            if row is None or not self._visible(row, user, is_captain):
                return False
            await repository.mark_read(notification_id, user["id"])
            return True

    @staticmethod
    def _visible(row: Any, user: dict[str, Any], is_captain: bool) -> bool:
        target = row.target_type
        team_id = user.get("teamId") or user.get("team_id")
        if target == "all":
            return True
        if target == "admins":
            return user.get("role") == "admin"
        if target == "user":
            return row.target_id == user.get("id")
        if target == "teams":
            return bool(team_id)
        if target == "team":
            return row.target_id == team_id
        if target == "captain":
            return bool(team_id and row.target_id == team_id and is_captain)
        if target == "captains":
            return bool(team_id and is_captain)
        return False
