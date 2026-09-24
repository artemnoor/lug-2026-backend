"""SQLAlchemy adapter for admin snapshots and review mutations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from ...db.models import (
    AchievementRow,
    AuditLogRow,
    NotificationRow,
    TeamRow,
    UserRow,
)
from .ports import AdminRepository


class SqlAlchemyAdminRepository(AdminRepository):
    def __init__(self, session: Any) -> None:
        self.session = session

    async def overview_rows(self) -> dict[str, Any]:
        return {
            "users": list(
                (await self.session.scalars(select(UserRow).where(UserRow.role != "admin"))).all()
            ),
            "teams": list((await self.session.scalars(select(TeamRow))).all()),
            "achievements": list((await self.session.scalars(select(AchievementRow))).all()),
            "notifications": list(
                (
                    await self.session.scalars(
                        select(NotificationRow)
                        .order_by(NotificationRow.created_at.desc())
                        .limit(200)
                    )
                ).all()
            ),
            "audit": list(
                (
                    await self.session.scalars(
                        select(AuditLogRow).order_by(AuditLogRow.at.desc()).limit(100)
                    )
                ).all()
            ),
        }

    async def collection_rows(self, resource: str) -> list[Any]:
        if resource == "users":
            return list(
                (await self.session.scalars(select(UserRow).where(UserRow.role != "admin"))).all()
            )
        if resource == "teams":
            return list((await self.session.scalars(select(TeamRow))).all())
        return list((await self.session.scalars(select(AchievementRow))).all())

    async def audit_rows(self) -> list[Any]:
        return list(
            (
                await self.session.scalars(
                    select(AuditLogRow).order_by(AuditLogRow.at.desc()).limit(200)
                )
            ).all()
        )

    async def broadcast_targets(self) -> tuple[list[UserRow], list[TeamRow]]:
        users = list(
            (
                await self.session.scalars(
                    select(UserRow).where(UserRow.role != "admin", UserRow.email_verified.is_(True))
                )
            ).all()
        )
        teams = list((await self.session.scalars(select(TeamRow))).all())
        return users, teams
