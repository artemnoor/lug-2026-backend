"""Team lifecycle and registration application operations."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from ...common.projections import team_view, user_view
from ...common.time import now_utc
from ...core.config import EmailSettings
from ...core.database import UnitOfWork
from ...core.errors import ConflictError, NotFoundError, ValidationAppError
from ...core.security import hash_password, verification_hash
from . import domain
from .ports import TeamRepository

TeamRepositoryFactory = Callable[[Any], TeamRepository]


class TeamService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        email_settings: EmailSettings,
        email: Any,
        auth: Any,
        media: Any,
        logger: Any,
        portfolio: Any = None,
        notifications: Any = None,
        content: Any = None,
        repository_factory: TeamRepositoryFactory | None = None,
    ) -> None:
        self.uow_factory = uow_factory
        self.email_settings = email_settings
        self.email = email
        self.auth = auth
        self.media = media
        self.logger = logger
        self.portfolio = portfolio
        self.notifications = notifications
        self.content = content
        self.repository_factory = repository_factory

    def _repository(self, session: Any) -> TeamRepository:
        if self.repository_factory is None:
            raise RuntimeError("Team repository is not configured")
        return self.repository_factory(session)

    async def begin_registration(self, payload: dict[str, Any], kind: str) -> dict[str, Any]:
        values = domain.validate_registration(payload, kind == "team")
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            settings = await repository.get_settings()
            if not domain.registration_open(settings):
                raise ValidationAppError(
                    "Регистрация завершена или ещё не началась.", "REGISTRATION_CLOSED"
                )
            if await repository.get_user_by_email(values["email"]):
                raise ConflictError(
                    "Этот адрес электронной почты уже зарегистрирован.", "EMAIL_ALREADY_REGISTERED"
                )
            if kind == "team":
                if await repository.get_team_by_group(values["group"]):
                    raise ConflictError(
                        "Для этой учебной группы уже создана команда.", "GROUP_ALREADY_REGISTERED"
                    )
            else:
                invite = await repository.get_team_by_invite(
                    str(values.get("inviteCode", "")).strip().upper(), now_utc()
                )
                if invite is None:
                    raise NotFoundError("Приглашение неактивно.", "INVITE_INVALID")
                if len(await repository.get_members(invite.id)) >= invite.member_limit:
                    raise ConflictError(
                        "В команде уже достигнута заявленная вместимость.", "TEAM_CAPACITY_REACHED"
                    )
            upload = await self.media.get_upload_by_url(values["studentCardFile"])
            claim = self.media.verify_registration_claim(values.get("studentCardUploadToken", ""))
            if (
                upload is None
                or upload.get("scan_status") != "clean"
                or claim is None
                or claim.get("key") != values["studentCardFile"]
            ):
                raise ValidationAppError(
                    "Временная загрузка документа недействительна или истекла.",
                    "REGISTRATION_UPLOAD_CLAIM_INVALID",
                )
            if (
                not str(values.get("studentCardType", "")).startswith("image/")
                or int(values.get("studentCardSize") or 0) <= 0
            ):
                raise ValidationAppError(
                    "Некорректные параметры загруженного документа.",
                    "REGISTRATION_UPLOAD_METADATA_INVALID",
                )
            existing = await repository.get_pending_by_email(values["email"])
            values["kind"] = kind
            values["passwordHash"] = await hash_password(values["password"])
            values["inviteCode"] = str(values.get("inviteCode", "")).strip().upper()
            if kind == "team":
                team_data = domain.new_team_data(
                    values["group"],
                    values["teamName"],
                    int(values["totalStudentsInGroup"] or 1),
                    int(settings.get("inviteLifetimeDays", 30)),
                )
                values.update(
                    {
                        "inviteCode": team_data["invite_code"],
                        "inviteExpiresAt": team_data["invite_expires_at"].isoformat(),
                    }
                )
            code = __import__(
                "app.modules.auth.domain", fromlist=["new_verification_code"]
            ).new_verification_code()
            expires = now_utc() + timedelta(seconds=self.email_settings.verification_ttl_seconds)
            row = await repository.save_pending(
                values,
                verification_hash(self.email_settings.verification_secret, code, "email"),
                expires,
                existing.id if existing else None,
            )
            self.logger.info(
                "registration.pending", email=values["email"], verification_id=row.id, kind=kind
            )
            pending = {
                "verificationRequired": True,
                "verificationId": row.id,
                "email": row.email,
                "expiresAt": expires.isoformat(),
                "message": "Код отправлен на почту. Проверьте входящие и папку «Спам».",
            }
        # External email delivery happens only after the database transaction
        # has committed, so a failed SMTP call cannot leave a phantom request
        # or a rolled-back request with an already sent code.
        await self.email.send(
            values["email"], "Подтверждение email — ЛУГ 2026", f"Ваш код подтверждения: {code}"
        )
        return pending

    async def verify_email(
        self, verification_id: str, code: str, user_agent: str = "", ip_address: str = ""
    ) -> tuple[dict[str, Any], str]:
        invalid_code = False
        user_row = None
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            row = await repository.get_pending(verification_id)
            if row is None:
                raise NotFoundError(
                    "Заявка на подтверждение не найдена или уже обработана.",
                    "VERIFICATION_NOT_FOUND",
                )
            expires_at = row.expires_at
            if expires_at.tzinfo is None:
                from datetime import timezone

                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now_utc():
                raise ValidationAppError("Код подтверждения истёк.", "EMAIL_CODE_EXPIRED")
            if row.attempts >= self.email_settings.verification_max_attempts:
                raise ValidationAppError(
                    "Превышено число попыток подтверждения.", "EMAIL_CODE_ATTEMPTS_EXCEEDED"
                )
            expected = verification_hash(self.email_settings.verification_secret, code, "email")
            if not __import__("hmac").compare_digest(expected, row.code_hash):
                await repository.increment_pending_attempt(verification_id)
                invalid_code = True
            else:
                try:
                    user_row = await repository.commit_pending(row, now_utc())
                except ValueError as exc:
                    raise ConflictError(
                        "Не удалось завершить регистрацию команды.", "REGISTRATION_CONFLICT"
                    ) from exc
        if invalid_code:
            raise ValidationAppError("Неверный код подтверждения.", "EMAIL_CODE_INVALID")
        assert user_row is not None
        token = await self.auth.issue_session(user_row.id, user_agent, ip_address)
        await self.media.claim_upload_for_user(user_row.student_card_file, user_row.id)
        return user_view(user_row), token

    async def resend_email_code(self, verification_id: str) -> dict[str, Any]:
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            row = await repository.get_pending(verification_id)
            if row is None:
                raise NotFoundError(
                    "Заявка на подтверждение не найдена или уже обработана.",
                    "VERIFICATION_NOT_FOUND",
                )
            last_sent_at = row.last_sent_at
            if last_sent_at.tzinfo is None:
                from datetime import timezone

                last_sent_at = last_sent_at.replace(tzinfo=timezone.utc)
            elapsed = (now_utc() - last_sent_at).total_seconds()
            if elapsed < self.email_settings.verification_cooldown_seconds:
                raise ValidationAppError(
                    f"Новый код можно запросить через {max(1, int(self.email_settings.verification_cooldown_seconds - elapsed))} сек.",
                    "VERIFICATION_COOLDOWN",
                )
            code = __import__(
                "app.modules.auth.domain", fromlist=["new_verification_code"]
            ).new_verification_code()
            expires = now_utc() + timedelta(seconds=self.email_settings.verification_ttl_seconds)
            await repository.update_pending_code(
                row,
                verification_hash(self.email_settings.verification_secret, code, "email"),
                expires,
                now_utc(),
            )
            email = row.email
        await self.email.send(
            email, "Подтверждение email — ЛУГ 2026", f"Ваш код подтверждения: {code}"
        )
        return {
            "verificationRequired": True,
            "verificationId": verification_id,
            "email": email,
            "expiresAt": expires.isoformat(),
            "message": "Новый код отправлен на почту.",
        }

    async def get_invite(self, code: str) -> dict[str, Any]:
        async with self.uow_factory() as uow:
            row = await self._repository(uow.session).get_team_by_invite(code.upper(), now_utc())
            if row is None:
                raise NotFoundError(
                    "Приглашение не найдено, отозвано или истекло.", "INVITE_INVALID"
                )
            return {
                "team": {
                    "name": row.name,
                    "group": row.group,
                    "inviteExpiresAt": row.invite_expires_at.isoformat()
                    if row.invite_expires_at
                    else None,
                }
            }

    async def get_team(self, team_id: str) -> dict[str, Any] | None:
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            row = await repository.get_team(team_id)
            if row is None:
                return None
            members = [user_view(member) for member in await repository.get_members(team_id)]
            return team_view(row, members)

    async def dashboard(self, user: dict[str, Any]) -> dict[str, Any] | None:
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            user_row = await repository.get_user(user["id"])
            if user_row is None:
                return None
            team = await repository.get_team(user_row.team_id) if user_row.team_id else None
            member_rows = await repository.get_members(team.id) if team else []
            members = [user_view(member) for member in member_rows]
            settings = await repository.get_settings()
            result: dict[str, Any] = {
                "user": user_view(user_row),
                "team": team_view(team, members) if team else None,
                "members": members,
                "achievements": [],
                "notifications": [],
                "settings": settings,
            }
            if team:
                team_projection = result["team"]
                assert team_projection is not None
                team_projection["quota"] = domain.quota(
                    team, len(member_rows), int(settings.get("minTeamPercentage", 60))
                )
                team_projection["isAdmitted"] = domain.is_admitted(
                    team, member_rows, int(settings.get("minTeamPercentage", 60))
                )
        if self.portfolio is not None:
            result["achievements"] = await self.portfolio.list_for_user(user["id"])
        if self.notifications is not None:
            result["notifications"] = await self.notifications.list_for_user(user)
        if self.content is not None:
            result["settings"] = await self.content.get_settings()
        return result

    async def update_team(self, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            user_row = await repository.get_user(user["id"])
            if user_row is None or user_row.team_id is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            team = await repository.get_team(user_row.team_id)
            if team is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            domain.check_captain({"captainId": team.captain_id}, user)
            allowed = {"name": "name", "description": "description", "flagUrl": "flag_url"}
            changes = {
                target: str(payload[key]).strip()
                for key, target in allowed.items()
                if key in payload
            }
            for key, value in changes.items():
                if key in {"name", "description"} and len(value) > (200 if key == "name" else 2000):
                    raise ValidationAppError("Слишком длинное поле команды.", "TEAM_FIELD_TOO_LONG")
            await repository.update_team(team, changes)
            return team_view(
                team, [user_view(member) for member in await repository.get_members(team.id)]
            )

    async def rotate_invite(self, user: dict[str, Any]) -> dict[str, Any]:
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            user_row = await repository.get_user(user["id"])
            if user_row is None or user_row.team_id is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            team = await repository.get_team(user_row.team_id)
            if team is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            domain.check_captain({"captainId": team.captain_id}, user)
            settings = await repository.get_settings()
            data = domain.new_team_data(
                team.group,
                team.name,
                team.member_limit,
                int(settings.get("inviteLifetimeDays", 30)),
            )
            await repository.update_team(
                team,
                {
                    "invite_code": data["invite_code"],
                    "invite_expires_at": data["invite_expires_at"],
                    "invite_status": "active",
                },
            )
            return {
                "inviteCode": team.invite_code,
                "inviteExpiresAt": team.invite_expires_at.isoformat()
                if team.invite_expires_at
                else None,
            }

    async def confirm_quota(self, team_id: str, confirmed: bool, actor_id: str) -> dict[str, Any]:
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            team = await repository.get_team(team_id)
            if team is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            await repository.update_team(team, {"quota_confirmed": confirmed})
            await repository.save_audit(
                actor_id,
                "team.quota.updated",
                "team",
                team_id,
                {"confirmed": confirmed},
            )
            members = [user_view(member) for member in await repository.get_members(team_id)]
            return team_view(team, members)

    async def review_team(
        self, team_id: str, payload: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        field = str(payload.get("field", ""))
        status = str(payload.get("status", ""))
        comment = str(payload.get("comment") or "").strip()
        if field not in {"name", "group", "flag", "description"} or status not in {
            "pending",
            "approved",
            "rejected",
        }:
            raise ValidationAppError(
                "Недопустимое решение по данным команды.", "TEAM_REVIEW_INVALID"
            )
        if status == "rejected" and not comment:
            raise ValidationAppError(
                "При отклонении обязательно укажите причину.", "REVIEW_COMMENT_REQUIRED"
            )
        field_map = {
            "name": "review_name_status",
            "group": "review_group_status",
            "flag": "review_flag_status",
            "description": "review_description_status",
        }
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            team = await repository.get_team(team_id)
            if team is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            await repository.update_team(
                team, {field_map[field]: status, "review_comment": comment}
            )
            await repository.save_audit(
                actor_id,
                "team.reviewed",
                "team",
                team_id,
                {"field": field, "status": status, "comment": comment},
            )
            members = [user_view(member) for member in await repository.get_members(team_id)]
            return team_view(team, members)

    async def remove_member(self, team_id: str, user_id: str, actor_id: str) -> None:
        async with self.uow_factory() as uow:
            repository = self._repository(uow.session)
            team = await repository.get_team(team_id)
            if team is None:
                raise NotFoundError("Команда не найдена.", "TEAM_NOT_FOUND")
            member = await repository.get_user(user_id)
            if member is None or member.team_id != team_id:
                raise NotFoundError("Участник не найден.", "MEMBER_NOT_FOUND")
            if member.id == team.captain_id:
                raise ValidationAppError(
                    "Капитана нельзя удалить из команды.", "CAPTAIN_CANNOT_BE_REMOVED"
                )
            member.team_id = None
            await repository.save_user(member)
            await repository.save_audit(
                actor_id,
                "team.member.removed",
                "user",
                user_id,
                {"teamId": team_id},
            )
