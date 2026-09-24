"""SQLAlchemy upload ownership adapter."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update

from ...db.models import AchievementRow, TeamRow, UploadRow, UserRow
from .ports import MediaRepository


class SqlAlchemyMediaRepository(MediaRepository):
    def __init__(self, session: Any) -> None:
        self.session = session

    async def get_by_url(self, url: str) -> UploadRow | None:
        return await self.session.scalar(select(UploadRow).where(UploadRow.url == url))

    async def save(
        self, metadata: dict[str, Any], owner_user_id: str | None, claim_subject: str | None
    ) -> UploadRow:
        row = UploadRow(
            upload_id=metadata["upload_id"],
            owner_user_id=owner_user_id,
            claim_subject=claim_subject,
            url=metadata["url"],
            storage_key=metadata["storage_key"],
            storage_path=metadata.get("storage_path", ""),
            original_name=metadata["original_name"],
            kind=metadata["kind"],
            content_type=metadata["content_type"],
            size_bytes=metadata["size_bytes"],
            status=metadata.get("status", "uploaded"),
            scan_status=metadata.get("scan_status", "pending"),
            scan_reason=metadata.get("scan_reason", ""),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def claim(self, url: str, user_id: str) -> None:
        await self.session.execute(
            update(UploadRow)
            .where(UploadRow.url == url)
            .values(owner_user_id=user_id, claim_subject=None)
        )
        await self.session.flush()

    async def count_for_user(self, user_id: str) -> tuple[int, int]:
        row = (
            await self.session.execute(
                select(
                    func.count(UploadRow.upload_id),
                    func.coalesce(func.sum(UploadRow.size_bytes), 0),
                ).where(UploadRow.owner_user_id == user_id)
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    async def is_team_member(self, user_id: str, team_id: str) -> bool:
        return bool(
            await self.session.scalar(
                select(UserRow.id).where(UserRow.id == user_id, UserRow.team_id == team_id)
            )
        )

    async def is_team_shared(self, url: str, team_id: str) -> bool:
        achievement_upload = await self.session.scalar(
            select(AchievementRow.id)
            .join(UserRow, UserRow.id == AchievementRow.user_id)
            .join(UploadRow, UploadRow.upload_id == AchievementRow.file_upload_id)
            .where(UploadRow.url == url, UserRow.team_id == team_id)
        )
        if achievement_upload:
            return True
        return bool(
            await self.session.scalar(
                select(TeamRow.id).where(TeamRow.id == team_id, TeamRow.flag_url == url)
            )
        )
