"""Admin interface façade over domain-owned review and content operations."""

from __future__ import annotations

from typing import Any, Callable

from ...common.projections import (
    achievement_view,
    notification_view,
    team_view,
    user_view,
    video_view,
)
from ...core.database import UnitOfWork
from ...core.errors import NotFoundError, ValidationAppError
from ..content.contracts import ContentWriter
from ..notifications.contracts import NotificationWriter
from ..portfolio.contracts import PortfolioAdminOperations
from ..teams.contracts import TeamAdminOperations, is_admitted, quota
from ..users.contracts import UserAdminOperations
from ..video.contracts import VideoAdminOperations
from .ports import AdminRepository

AdminRepositoryFactory = Callable[[Any], AdminRepository]


class AdminService:
    """Admin-only orchestration; persistence remains behind the admin read port."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        content: ContentWriter,
        notifications: NotificationWriter,
        teams: TeamAdminOperations,
        users: UserAdminOperations,
        portfolio: PortfolioAdminOperations,
        video: VideoAdminOperations,
        email: Any,
        logger: Any,
        repository_factory: AdminRepositoryFactory,
    ) -> None:
        self.uow_factory = uow_factory
        self.content = content
        self.notifications = notifications
        self.teams = teams
        self.users = users
        self.portfolio = portfolio
        self.video = video
        self.email = email
        self.logger = logger
        self.repository_factory = repository_factory

    def _repository(self, session: Any) -> AdminRepository:
        return self.repository_factory(session)

    async def overview(self) -> dict[str, Any]:
        settings = await self.content.get_settings()
        async with self.uow_factory() as uow:
            rows = await self._repository(uow.session).overview_rows()
            users = rows["users"]
            teams = rows["teams"]
            achievements = rows["achievements"]
            notifications = rows["notifications"]
            audit = rows["audit"]
            users_by_team: dict[str, list[Any]] = {}
            users_by_id = {user.id: user for user in users}
            for user in users:
                if user.team_id:
                    users_by_team.setdefault(user.team_id, []).append(user)
            teams_view = []
            for team in teams:
                members = users_by_team.get(team.id, [])
                member_views = [user_view(member) for member in members]
                team_data = team_view(team, member_views)
                team_data["quota"] = quota(
                    team, len(members), int(settings.get("minTeamPercentage", 60))
                )
                team_data["isAdmitted"] = is_admitted(
                    team, members, int(settings.get("minTeamPercentage", 60))
                )
                team_data["review"] = {
                    "name": {"status": team.review_name_status},
                    "group": {"status": team.review_group_status},
                    "flag": {"status": team.review_flag_status},
                    "description": {"status": team.review_description_status},
                    "members": {
                        "status": "pending"
                        if any(member.identity_status == "pending" for member in members)
                        else "approved"
                    },
                }
                team_member_ids = {member.id for member in members}
                team_data["achievements"] = [
                    achievement_view(item, user_view(users_by_id.get(item.user_id)))
                    for item in achievements
                    if item.user_id in team_member_ids
                ]
                team_data["workflow"] = {
                    "key": "review"
                    if any(item["status"] == "pending" for item in team_data["achievements"])
                    else "new",
                    "label": "На проверке",
                }
                teams_view.append(team_data)
            return {
                "settings": settings,
                "summary": {
                    "teams": len(teams),
                    "users": len(users),
                    "achievements": len(achievements),
                    "notifications": len(notifications),
                    "pendingAchievements": sum(item.status == "pending" for item in achievements),
                    "pendingIdentity": sum(item.identity_status == "pending" for item in users),
                    "pendingVideos": sum(team.video_status == "pending" for team in teams),
                    "unreadNotifications": len(notifications),
                },
                "teams": teams_view,
                "users": [user_view(user) for user in users],
                "achievements": [
                    achievement_view(item, user_view(users_by_id.get(item.user_id)))
                    for item in achievements
                ],
                "videos": [
                    {
                        "teamId": team.id,
                        "teamName": team.name,
                        "group": team.group,
                        "videoCard": video_view(team),
                    }
                    for team in teams
                ],
                "notifications": [notification_view(item) for item in notifications],
                "adminNotifications": [
                    notification_view(item)
                    for item in notifications
                    if item.target_type == "admins"
                ],
                "auditLog": [
                    {
                        "id": item.id,
                        "action": item.action,
                        "entityType": item.entity_type,
                        "entityId": item.entity_id,
                        "payload": item.payload,
                        "at": item.at.isoformat(),
                    }
                    for item in audit
                ],
            }

    async def collection(
        self, resource: str, limit: int, offset: int, query: str, status: str
    ) -> dict[str, Any]:
        if resource not in {"users", "teams", "achievements"}:
            raise NotFoundError("Раздел админ-панели не найден.", "ADMIN_RESOURCE_NOT_FOUND")
        async with self.uow_factory() as uow:
            rows = await self._repository(uow.session).collection_rows(resource)
            if resource == "users":
                items = [
                    user_view(row)
                    for row in rows
                    if not query or query.lower() in f"{row.fio} {row.email}".lower()
                ]
            elif resource == "teams":
                items = [
                    team_view(row)
                    for row in rows
                    if not query or query.lower() in f"{row.name} {row.group}".lower()
                ]
            else:
                items = [
                    achievement_view(row)
                    for row in rows
                    if (status == "all" or row.status == status)
                    and (not query or query.lower() in f"{row.title} {row.category}".lower())
                ]
            return {
                "items": items[offset : offset + limit],
                "total": len(items),
                "limit": limit,
                "offset": offset,
            }

    async def audit(self) -> list[dict[str, Any]]:
        async with self.uow_factory() as uow:
            rows = await self._repository(uow.session).audit_rows()
            return [
                {
                    "id": row.id,
                    "actorUserId": row.actor_user_id,
                    "action": row.action,
                    "entityType": row.entity_type,
                    "entityId": row.entity_id,
                    "payload": row.payload,
                    "at": row.at.isoformat(),
                }
                for row in rows
            ]

    async def confirm_quota(self, team_id: str, confirmed: bool, actor_id: str) -> dict[str, Any]:
        return await self.teams.confirm_quota(team_id, confirmed, actor_id)

    async def review_team(
        self, team_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        return await self.teams.review_team(team_id, payload, actor_id)

    async def remove_member(self, team_id: str, user_id: str, actor_id: str) -> None:
        await self.teams.remove_member(team_id, user_id, actor_id)

    async def review_identity(
        self, user_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        return await self.users.review_identity(user_id, payload, actor_id)

    async def review_achievement(
        self, achievement_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        return await self.portfolio.review_achievement(achievement_id, payload, actor_id)

    async def review_video(
        self, team_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        return await self.video.review_video(team_id, payload, actor_id)

    async def update_settings(self, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
        return await self.content.update_settings(payload, actor_id)

    async def broadcast(self, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
        target_type = str(payload.get("targetType") or "all")
        title, message, kind = (
            str(payload.get("title") or "").strip(),
            str(payload.get("message") or "").strip(),
            payload.get("kind"),
        )
        if (
            kind not in {None, "system"}
            or not title
            or len(title) > 120
            or "\n" in title
            or not message
            or len(message) > 1000
        ):
            raise ValidationAppError(
                "Укажите адресатов, заголовок и текст сообщения.", "BROADCAST_PAYLOAD_INVALID"
            )
        if target_type not in {"all", "teams", "captains", "team", "captain", "user"}:
            raise ValidationAppError("Укажите корректную аудиторию.", "BROADCAST_PAYLOAD_INVALID")
        target_id = str(payload.get("targetId") or "")
        async with self.uow_factory() as uow:
            users, teams = await self._repository(uow.session).broadcast_targets()
        if target_type == "user" and not any(user.id == target_id for user in users):
            raise NotFoundError("Пользователь не найден.", "USER_NOT_FOUND")
        if target_type in {"team", "captain"} and not any(team.id == target_id for team in teams):
            raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
        if target_type == "user":
            recipients = [user for user in users if user.id == target_id]
        elif target_type in {"team", "captain"}:
            recipients = [
                user
                for user in users
                if user.team_id == target_id
                and (
                    target_type == "team"
                    or any(team.id == target_id and team.captain_id == user.id for team in teams)
                )
            ]
        elif target_type == "captains":
            captains = {team.captain_id for team in teams}
            recipients = [user for user in users if user.id in captains]
        else:
            recipients = users
        await self.notifications.create(
            target_type, target_id, "system", title, message, actor_id, True
        )
        sent = 0
        failed = 0
        for recipient in recipients:
            try:
                await self.email.send(recipient.email, title, message)
                sent += 1
            except Exception as exc:
                failed += 1
                self.logger.warning(
                    "notification.email_failed",
                    recipient=recipient.email,
                    error_type=type(exc).__name__,
                )
        return {
            "success": True,
            "emailRecipients": len(recipients),
            "emailSent": sent,
            "emailFailed": failed,
            "emailMode": self.email.settings.mode,
        }
