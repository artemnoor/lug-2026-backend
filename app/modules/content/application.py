"""Settings, public results, and competition content operations."""

from __future__ import annotations

import math
from typing import Any, Callable

from ...common.projections import settings_view
from ...common.time import now_utc, parse_datetime
from ...core.database import UnitOfWork
from ...core.errors import ValidationAppError
from .contracts import default_settings
from .ports import ContentRepository

ContentRepositoryFactory = Callable[[Any], ContentRepository]


class ContentService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        logger: Any,
        repository_factory: ContentRepositoryFactory,
    ) -> None:
        self.uow_factory = uow_factory
        self.logger = logger
        self.repository_factory = repository_factory

    async def get_settings(self) -> dict[str, Any]:
        async with self.uow_factory() as uow:
            data = await self.repository_factory(uow.session).get_settings()
            return settings_view(data)

    async def ensure_settings(self) -> None:
        async with self.uow_factory() as uow:
            await self.repository_factory(uow.session).ensure_settings(default_settings())

    async def get_results(self) -> dict[str, Any]:
        settings = await self.get_settings()
        start = parse_datetime(settings.get("resultsStart"))
        if start and start > now_utc():
            return {"published": False, "availableFrom": settings.get("resultsStart"), "teams": []}
        async with self.uow_factory() as uow:
            teams, users, achievements = await self.repository_factory(
                uow.session
            ).get_result_rows()
            result = []
            for team in teams:
                members = [user for user in users if user.team_id == team.id]
                required = math.ceil(
                    team.member_limit * int(settings.get("minTeamPercentage", 60)) / 100
                )
                admitted = (
                    team.quota_confirmed
                    and len(members) >= required
                    and bool(members)
                    and all(member.identity_status == "approved" for member in members)
                )
                score = sum(
                    float(item.points or 0)
                    for item in achievements
                    if any(member.id == item.user_id for member in members)
                )
                if team.video_status == "approved":
                    score += float(team.video_score or 0)
                if admitted and all(
                    getattr(team, name) == "approved"
                    for name in (
                        "review_name_status",
                        "review_group_status",
                        "review_flag_status",
                        "review_description_status",
                    )
                ):
                    result.append(
                        {
                            "id": team.id,
                            "name": team.name,
                            "group": team.group,
                            "score": score,
                            "admitted": True,
                        }
                    )
            result.sort(key=lambda item: (-float(item["score"]), str(item["name"])))
            return {
                "published": True,
                "availableFrom": settings.get("resultsStart"),
                "teams": result,
            }

    async def update_settings(self, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
        allowed = {
            "registrationStart",
            "registrationDeadline",
            "portfolioStart",
            "portfolioDeadline",
            "videoStart",
            "videoDeadline",
            "resultsStart",
            "resultsDeadline",
            "isRegistrationOpen",
            "minTeamPercentage",
            "inviteLifetimeDays",
            "content",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValidationAppError(
                "Некорректные поля настроек.",
                "SETTINGS_FIELDS_INVALID",
                {"fields": sorted(unknown)},
            )
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            data = await repository.get_settings()
            data.update({key: value for key, value in payload.items() if key in allowed})
            for start_key, end_key in (
                ("registrationStart", "registrationDeadline"),
                ("portfolioStart", "portfolioDeadline"),
                ("videoStart", "videoDeadline"),
                ("resultsStart", "resultsDeadline"),
            ):
                start, end = parse_datetime(data.get(start_key)), parse_datetime(data.get(end_key))
                if start is None or end is None or start > end:
                    raise ValidationAppError(
                        "Проверьте интервалы дат настроек.", "SETTINGS_DATES_INVALID"
                    )
            if not 1 <= int(data.get("minTeamPercentage", 60)) <= 100:
                raise ValidationAppError(
                    "Процент допуска должен быть от 1 до 100.", "SETTINGS_PERCENTAGE_INVALID"
                )
            await repository.save_settings(data)
            return data
