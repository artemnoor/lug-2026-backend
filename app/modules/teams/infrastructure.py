"""SQLAlchemy team, user, settings, and registration persistence adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update

from ...common.time import now_utc, parse_datetime
from ...db.models import AuditLogRow, EmailVerificationRow, SettingRow, TeamRow, UserRow
from ..content.contracts import default_settings
from .ports import TeamRepository


class SqlAlchemyTeamRepository(TeamRepository):
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_team(self, team_id: str) -> TeamRow | None:
        return await self.session.get(TeamRow, team_id)

    async def get_team_by_group(self, group: str) -> TeamRow | None:
        return await self.session.scalar(
            select(TeamRow).where(TeamRow.group == group.strip().upper())
        )

    async def get_team_by_invite(self, code: str, now: datetime) -> TeamRow | None:
        return await self.session.scalar(
            select(TeamRow).where(
                TeamRow.invite_code == code,
                TeamRow.invite_status == "active",
                TeamRow.invite_expires_at >= now,
            )
        )

    async def get_user(self, user_id: str) -> UserRow | None:
        return await self.session.get(UserRow, user_id)

    async def get_user_by_email(self, email: str) -> UserRow | None:
        return await self.session.scalar(select(UserRow).where(UserRow.email == email))

    async def get_members(self, team_id: str) -> list[UserRow]:
        return list(
            (
                await self.session.scalars(
                    select(UserRow).where(UserRow.team_id == team_id).order_by(UserRow.created_at)
                )
            ).all()
        )

    async def get_settings(self) -> dict[str, Any]:
        row = await self.session.get(SettingRow, 1)
        return {**default_settings(), **(row.data if row else {})}

    async def save_pending(
        self,
        values: dict[str, Any],
        code_hash: str,
        expires_at: datetime,
        verification_id: str | None = None,
    ) -> EmailVerificationRow:
        existing = await self.get_pending_by_email(values["email"])
        row = existing or EmailVerificationRow(
            id=verification_id or str(uuid4()),
            email=values["email"],
            purpose="registration",
            password_hash=values["passwordHash"],
            code_hash=code_hash,
            expires_at=expires_at,
            last_sent_at=now_utc(),
        )
        row.payload = {
            key: value
            for key, value in values.items()
            if key
            not in {
                "password",
                "passwordHash",
                "studentCardUploadToken",
                "studentCardSize",
                "studentCardType",
            }
        }
        row.password_hash = values["passwordHash"]
        row.code_hash = code_hash
        row.attempts = 0
        row.expires_at = expires_at
        row.last_sent_at = now_utc()
        if existing is None:
            self.session.add(row)
        await self.session.flush()
        return row

    async def get_pending(self, verification_id: str) -> EmailVerificationRow | None:
        return await self.session.get(EmailVerificationRow, verification_id)

    async def get_pending_by_email(self, email: str) -> EmailVerificationRow | None:
        return await self.session.scalar(
            select(EmailVerificationRow).where(
                EmailVerificationRow.email == email, EmailVerificationRow.purpose == "registration"
            )
        )

    async def increment_pending_attempt(self, verification_id: str) -> None:
        await self.session.execute(
            update(EmailVerificationRow)
            .where(EmailVerificationRow.id == verification_id)
            .values(attempts=EmailVerificationRow.attempts + 1)
        )

    async def update_pending_code(
        self, row: EmailVerificationRow, code_hash: str, expires_at: datetime, now: datetime
    ) -> None:
        row.code_hash = code_hash
        row.expires_at = expires_at
        row.attempts = 0
        row.last_sent_at = now
        await self.session.flush()

    async def commit_pending(self, row: EmailVerificationRow, now: datetime) -> UserRow:
        values = dict(row.payload)
        team: TeamRow | None = None
        if values.get("kind") == "participant":
            invite_code = str(values.get("inviteCode", "")).upper()
            team = await self.get_team_by_invite(invite_code, now)
            if team is None:
                raise ValueError("invite missing")
            if len(await self.get_members(team.id)) >= team.member_limit:
                raise ValueError("team capacity")
        else:
            invite_expires_at = parse_datetime(values.get("inviteExpiresAt"))
            if invite_expires_at is None:
                raise ValueError("invite expiry missing")
            team = TeamRow(
                id=str(uuid4()),
                group=str(values["group"]).strip().upper(),
                name=str(values["teamName"]).strip(),
                captain_id=None,
                invite_code=values["inviteCode"],
                invite_status="active",
                invite_expires_at=invite_expires_at,
                member_limit=int(values.get("totalStudentsInGroup") or 1),
            )
            self.session.add(team)
            await self.session.flush()
        user = UserRow(
            id=str(uuid4()),
            email=row.email,
            password_hash=row.password_hash,
            role="participant",
            fio=str(values.get("fio", "")).strip(),
            phone=str(values.get("phone") or "").strip() or None,
            messenger=str(values.get("messenger") or "").strip(),
            messenger_contact=str(values.get("messengerContact") or "").strip(),
            telegram_account=str(values.get("telegramAccount") or "").strip(),
            team_id=team.id,
            email_verified=True,
            identity_status="pending",
            student_card_file=str(values.get("studentCardFile") or ""),
            consent_at=now,
        )
        self.session.add(user)
        await self.session.flush()
        if team.captain_id is None:
            team.captain_id = user.id
        await self.session.delete(row)
        await self.session.flush()
        return user

    async def update_team(self, team: TeamRow, changes: dict[str, Any]) -> None:
        for key, value in changes.items():
            setattr(team, key, value)
        await self.session.flush()

    async def save_user(self, user: UserRow) -> None:
        await self.session.flush()

    async def save_audit(
        self,
        actor_id: str | None,
        action: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditLogRow(
                id=str(uuid4()),
                actor_user_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
            )
        )
        await self.session.flush()
