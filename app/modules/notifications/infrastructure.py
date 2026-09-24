"""SQLAlchemy notification adapter."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select

from ...db.models import NotificationReadRow, NotificationRow, TeamRow
from .ports import NotificationRepository


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: Any) -> None:
        self.session = session

    async def create(
        self,
        target_type: str,
        target_id: str,
        kind: str,
        title: str,
        message: str,
        created_by: str | None,
        email_requested: bool,
    ) -> NotificationRow:
        row = NotificationRow(
            id=str(uuid4()),
            target_type=target_type,
            target_id=target_id,
            kind=kind,
            title=title,
            message=message,
            created_by=created_by,
            email_requested=email_requested,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, notification_id: str) -> NotificationRow | None:
        return await self.session.get(NotificationRow, notification_id)

    async def list_all(self) -> list[NotificationRow]:
        return list(
            (
                await self.session.scalars(
                    select(NotificationRow).order_by(NotificationRow.created_at.desc()).limit(200)
                )
            ).all()
        )

    async def read_ids(self, user_id: str) -> set[str]:
        result = await self.session.scalars(
            select(NotificationReadRow.notification_id).where(
                NotificationReadRow.user_id == user_id
            )
        )
        return set(result.all())

    async def mark_read(self, notification_id: str, user_id: str) -> None:
        existing = await self.session.get(
            NotificationReadRow, {"notification_id": notification_id, "user_id": user_id}
        )
        if existing is None:
            self.session.add(NotificationReadRow(notification_id=notification_id, user_id=user_id))
            await self.session.flush()

    async def is_captain(self, team_id: str, user_id: str) -> bool:
        return bool(
            await self.session.scalar(
                select(TeamRow.id).where(TeamRow.id == team_id, TeamRow.captain_id == user_id)
            )
        )
