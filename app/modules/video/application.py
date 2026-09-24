"""Video submission and scoring rules."""

from __future__ import annotations

from typing import Any, Callable

from ...common.projections import video_view
from ...core.database import UnitOfWork
from ...core.errors import AuthorizationError, NotFoundError, ValidationAppError
from ..media.contracts import MediaReader
from ..teams.contracts import check_captain, video_open
from .ports import VideoRepository

VideoRepositoryFactory = Callable[[Any], VideoRepository]


class VideoService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        logger: Any,
        media: MediaReader,
        repository_factory: VideoRepositoryFactory,
    ) -> None:
        self.uow_factory = uow_factory
        self.logger = logger
        self.media = media
        self.repository_factory = repository_factory

    async def get_for_team(self, team_id: str) -> dict[str, Any] | None:
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).get_team(team_id)
            return video_view(row) if row else None

    async def score_for_team(self, team_id: str) -> float:
        async with self.uow_factory() as uow:
            row = await self.repository_factory(uow.session).get_team(team_id)
            return float(row.video_score or 0) if row else 0.0

    async def update(self, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        url = str(payload.get("url") or payload.get("videoUrl") or "").strip()
        file_url = str(payload.get("fileUrl") or "").strip()
        if not url and not file_url:
            raise ValidationAppError("Укажите ссылку или файл видео.", "VIDEO_FIELDS_INVALID")
        if url and domain_video_provider(url) is None:
            raise ValidationAppError("Ссылка на видео не поддерживается.", "VIDEO_URL_INVALID")
        if file_url:
            upload = await self.media.get_upload_by_url(file_url)
            if (
                upload is None
                or upload.get("owner_user_id") != user["id"]
                or upload.get("scan_status") != "clean"
            ):
                raise AuthorizationError(
                    "Файл видео принадлежит другому пользователю.", "UPLOAD_NOT_OWNED"
                )
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            owner = await repository.get_user(user["id"])
            if owner is None or owner.team_id is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            team = await repository.get_team(owner.team_id)
            if team is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            check_captain({"captainId": team.captain_id}, user)
            settings = await repository.get_settings()
            if not video_open(settings):
                raise AuthorizationError("Приём видео сейчас закрыт.", "VIDEO_CLOSED")
            team.video_url = url
            team.video_file_url = file_url
            team.video_status = "pending"
            team.video_comment = ""
            await repository.update_team(
                team,
                {
                    "video_url": url,
                    "video_file_url": file_url,
                    "video_status": "pending",
                    "video_comment": "",
                },
            )
            result = video_view(team)
        self.logger.info("video.updated", user_id=user["id"], team_id=team.id)
        return result

    async def review_video(
        self, team_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        status = str(payload.get("status", ""))
        comment = str(payload.get("comment") or "").strip()
        if status not in {"pending", "approved", "rejected"}:
            raise ValidationAppError("Недопустимый статус видео.", "VIDEO_REVIEW_INVALID")
        if status == "rejected" and not comment:
            raise ValidationAppError(
                "При отклонении обязательно укажите причину.", "REVIEW_COMMENT_REQUIRED"
            )
        limits = {"topic": 8, "creativity": 8, "quality": 5, "vfx": 2}
        raw_scores = payload.get("criteriaScores") or {}
        scores = {key: float(raw_scores.get(key, 0)) for key in limits}
        if any(value < 0 or value > limits[key] for key, value in scores.items()):
            raise ValidationAppError(
                "Оценка критерия выходит за допустимый диапазон.", "VIDEO_SCORE_INVALID"
            )
        async with self.uow_factory() as uow:
            repository = self.repository_factory(uow.session)
            team = await repository.get_team(team_id)
            if team is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            await repository.update_team(
                team,
                {
                    "video_status": status,
                    "video_comment": comment,
                    "video_criteria_scores": scores,
                    "video_score": sum(scores.values()),
                },
            )
            result = video_view(team)
        self.logger.info("video.reviewed", actor_id=actor_id, team_id=team_id, status=status)
        return result


def domain_video_provider(url: str) -> str | None:
    import re
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path
    if host == "rutube.ru" or host.endswith(".rutube.ru"):
        return (
            "rutube" if re.search(r"/(?:video|shorts|play/embed)/[a-z0-9_-]+", path, re.I) else None
        )
    if (
        host == "vk.com"
        or host.endswith(".vk.com")
        or host in {"vkvideo.ru", "vk.ru"}
        or host.endswith((".vkvideo.ru", ".vk.ru"))
    ):
        return (
            "vk"
            if re.search(r"/(?:video|clip)-?\d+_\d+", path, re.I)
            or (
                path.lower().endswith("/video_ext.php")
                and parse_qs(parsed.query).get("oid")
                and parse_qs(parsed.query).get("id")
            )
            else None
        )
    if host in {"disk.yandex.ru", "yadi.sk"} or host.endswith((".disk.yandex.ru", ".yadi.sk")):
        return "yandex-disk" if re.search(r"/(?:d|i)/[^/]+", path, re.I) else None
    return None
