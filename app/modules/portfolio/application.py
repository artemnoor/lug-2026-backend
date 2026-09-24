"""Portfolio application operations."""

from __future__ import annotations

from typing import Any, Callable

from ...common.projections import achievement_view
from ...core.database import UnitOfWork
from ...core.errors import AuthorizationError, NotFoundError, ValidationAppError
from ..teams.contracts import portfolio_open
from .ports import PortfolioRepository

PortfolioRepositoryFactory = Callable[[Any], PortfolioRepository]


class PortfolioService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        media: Any,
        logger: Any,
        repository_factory: PortfolioRepositoryFactory,
        settings_reader: Any,
    ) -> None:
        self.uow_factory = uow_factory
        self.media = media
        self.logger = logger
        self.repository_factory = repository_factory
        self.settings_reader = settings_reader

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        async with self.uow_factory() as uow:
            rows = await self.repository_factory(uow.session).list_for_user(user_id)
            return [achievement_view(row) for row in rows]

    async def create(self, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("direction") not in {"science", "public", "sport", "culture"}:
            raise ValidationAppError(
                "Укажите корректное направление.", "ACHIEVEMENT_FIELDS_INVALID"
            )
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            owner = await repository.get_user(user["id"])
            if owner is None:
                raise NotFoundError("Пользователь не найден.", "USER_NOT_FOUND")
            settings = await self.settings_reader.get_settings()
            if not portfolio_open(settings):
                raise AuthorizationError("Приём достижений сейчас закрыт.", "PORTFOLIO_CLOSED")
            file_url = str(payload.get("fileUrl") or "")
            if file_url:
                upload = await self.media.get_upload_by_url(file_url)
                if (
                    upload is None
                    or upload.get("owner_user_id") != owner.id
                    or upload.get("scan_status") != "clean"
                ):
                    raise AuthorizationError(
                        "Файл достижения принадлежит другому пользователю.", "UPLOAD_NOT_OWNED"
                    )
            values = {
                "user_id": owner.id,
                "title": str(payload.get("title", "")).strip(),
                "direction": payload["direction"],
                "category": str(payload.get("category", "")).strip(),
                "details": str(payload.get("details", "")).strip(),
                "file_url": file_url,
                "file_name": str(payload.get("fileName") or "Документ"),
                "status": "pending",
            }
            if not values["title"] or not values["category"]:
                raise ValidationAppError(
                    "Заполните название и категорию достижения.", "ACHIEVEMENT_FIELDS_INVALID"
                )
            row = await repository.create(values)
            result = achievement_view(row)
        self.logger.info(
            "portfolio.achievement.created", user_id=user["id"], achievement_id=result["id"]
        )
        return result

    async def delete(self, user: dict[str, Any], achievement_id: str) -> None:
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            row = await repository.get(achievement_id)
            if row is None:
                raise NotFoundError("Достижение не найдено.", "ACHIEVEMENT_NOT_FOUND")
            if row.user_id != user["id"] and user.get("role") != "admin":
                raise AuthorizationError("Недостаточно прав.", "ACHIEVEMENT_NOT_OWNED")
            await repository.delete(row)

    async def review_achievement(
        self, achievement_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        status = str(payload.get("status", ""))
        comment = str(payload.get("comment") or "").strip()
        if status not in {"pending", "approved", "rejected"}:
            raise ValidationAppError("Недопустимый статус материала.", "ACHIEVEMENT_REVIEW_INVALID")
        if status == "rejected" and not comment:
            raise ValidationAppError(
                "При отклонении обязательно укажите причину.", "REVIEW_COMMENT_REQUIRED"
            )
        points = payload.get("points")
        if points is not None and not 0 <= float(points) <= 100:
            raise ValidationAppError(
                "Баллы должны быть числом от 0 до 100.", "ACHIEVEMENT_POINTS_INVALID"
            )
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            row = await repository.get(achievement_id)
            if row is None:
                raise NotFoundError("Достижение не найдено.", "ACHIEVEMENT_NOT_FOUND")
            row.status = status
            row.review_comment = comment
            if points is not None:
                row.points = float(points)
            row.reviewed_by = actor_id
            await repository.save(row)
            result = achievement_view(row)
        self.logger.info(
            "achievement.reviewed", actor_id=actor_id, achievement_id=achievement_id, status=status
        )
        return result
