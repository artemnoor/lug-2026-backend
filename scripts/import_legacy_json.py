"""Import a frozen reference ``lug.json`` snapshot into the rebuilt schema.

This is deliberately an explicit operator command, never an application startup
side effect. Active sessions and pending verification/reset records are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

# Make the checked-out backend importable when the script is invoked directly as
# ``python scripts/import_legacy_json.py`` rather than with ``python -m``.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.database import UnitOfWork, create_engine, create_session_factory
from app.db.models import (
    AchievementRow,
    NotificationRow,
    SettingRow,
    TeamRow,
    UploadRow,
    UserRow,
)


def _value(item: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in item and item[name] is not None:
            return item[name]
    return default


def _text(item: dict[str, Any], *names: str, default: str = "") -> str:
    return str(_value(item, *names, default=default) or "").strip()


async def import_state(source: Path, database_url: str | None) -> dict[str, int]:
    raw = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("legacy state root must be an object")

    environment = dict(os.environ)
    if database_url:
        environment["LUG_DATABASE_URL"] = database_url
    settings = Settings.from_env(environment)
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)
    counts = {
        "settings": 0,
        "teams": 0,
        "users": 0,
        "uploads": 0,
        "achievements": 0,
        "notifications": 0,
        "skipped": 0,
    }

    async with UnitOfWork(session_factory) as uow:
        settings_data = raw.get("settings")
        if isinstance(settings_data, dict):
            row = await uow.session.get(SettingRow, 1)
            if row is None:
                uow.session.add(SettingRow(id=1, data=settings_data))
            else:
                row.data = {**row.data, **settings_data}
            counts["settings"] += 1

        for item in raw.get("teams", []):
            if not isinstance(item, dict):
                counts["skipped"] += 1
                continue
            team_id = _text(item, "id")
            if not team_id or await uow.session.get(TeamRow, team_id):
                counts["skipped"] += 1
                continue
            uow.session.add(
                TeamRow(
                    id=team_id,
                    group=_text(item, "group", "groupName", default=team_id),
                    name=_text(item, "name", "teamName", default=team_id),
                    description=_text(item, "description"),
                    captain_id=_value(item, "captainId", "captain_id"),
                    invite_code=_text(item, "inviteCode", "invite_code", default=uuid4().hex),
                    invite_status=_text(item, "inviteStatus", "invite_status", default="active"),
                    member_limit=int(_value(item, "memberLimit", "member_limit", default=1) or 1),
                    flag_url=_text(item, "flagUrl", "flag_url"),
                    quota_confirmed=bool(
                        _value(item, "quotaConfirmed", "quota_confirmed", default=False)
                    ),
                    is_admitted=bool(_value(item, "isAdmitted", "is_admitted", default=False)),
                    review_name_status=_text(item, "reviewNameStatus", default="pending"),
                    review_group_status=_text(item, "reviewGroupStatus", default="pending"),
                    review_flag_status=_text(item, "reviewFlagStatus", default="pending"),
                    review_description_status=_text(
                        item, "reviewDescriptionStatus", default="pending"
                    ),
                    review_comment=_text(item, "reviewComment"),
                    video_url=_text(item, "videoUrl"),
                    video_file_url=_text(item, "videoFileUrl"),
                    video_status=_text(item, "videoStatus", default="none"),
                    video_comment=_text(item, "videoComment"),
                    video_score=_value(item, "videoScore"),
                    video_criteria_scores=_value(item, "videoCriteriaScores", default={}) or {},
                )
            )
            counts["teams"] += 1
        await uow.session.flush()

        for item in raw.get("users", []):
            if not isinstance(item, dict):
                counts["skipped"] += 1
                continue
            user_id = _text(item, "id")
            password_hash = _text(item, "passwordHash", "password_hash")
            if not user_id or not password_hash or await uow.session.get(UserRow, user_id):
                counts["skipped"] += 1
                continue
            uow.session.add(
                UserRow(
                    id=user_id,
                    email=_text(item, "email").lower(),
                    password_hash=password_hash,
                    role=_text(item, "role", default="participant"),
                    fio=_text(item, "fio"),
                    phone=_text(item, "phone") or None,
                    messenger=_text(item, "messenger"),
                    messenger_contact=_text(item, "messengerContact", "messenger_contact"),
                    telegram_account=_text(item, "telegramAccount", "telegram_account"),
                    team_id=_value(item, "teamId", "team_id"),
                    email_verified=bool(_value(item, "emailVerified", default=False)),
                    identity_status=_text(item, "identityStatus", default="pending"),
                    identity_comment=_text(item, "identityComment"),
                    avatar_url=_text(item, "avatarUrl"),
                    student_card_file=_text(item, "studentCardFile"),
                    consent_at=None,
                )
            )
            counts["users"] += 1
        await uow.session.flush()

        for item in raw.get("uploads", []):
            if not isinstance(item, dict):
                counts["skipped"] += 1
                continue
            upload_id = _text(item, "uploadId", "upload_id")
            url = _text(item, "url")
            storage_key = _text(item, "storageKey", "storage_key", default=url)
            if (
                not upload_id
                or not url
                or not storage_key
                or await uow.session.get(UploadRow, upload_id)
            ):
                counts["skipped"] += 1
                continue
            uow.session.add(
                UploadRow(
                    upload_id=upload_id,
                    owner_user_id=_value(item, "ownerUserId", "owner_user_id"),
                    claim_subject=None,
                    url=url,
                    storage_key=storage_key,
                    storage_path=_text(item, "storagePath", "storage_path"),
                    original_name=_text(item, "originalName", "name", default="imported-file"),
                    kind=_text(item, "kind", default="attachment"),
                    content_type=_text(
                        item, "contentType", "content_type", default="application/octet-stream"
                    ),
                    size_bytes=int(_value(item, "size", "sizeBytes", "size_bytes", default=0) or 0),
                    status=_text(item, "status", default="uploaded"),
                    scan_status=_text(item, "scanStatus", "scan_status", default="pending"),
                    scan_reason=_text(item, "scanReason", "scan_reason"),
                )
            )
            counts["uploads"] += 1
        await uow.session.flush()

        for item in raw.get("achievements", []):
            if not isinstance(item, dict):
                counts["skipped"] += 1
                continue
            achievement_id = _text(item, "id")
            user_id = _text(item, "userId", "user_id")
            if (
                not achievement_id
                or not user_id
                or await uow.session.get(AchievementRow, achievement_id)
            ):
                counts["skipped"] += 1
                continue
            uow.session.add(
                AchievementRow(
                    id=achievement_id,
                    user_id=user_id,
                    title=_text(item, "title"),
                    direction=_text(item, "direction", default="science"),
                    category=_text(item, "category"),
                    details=_text(item, "details"),
                    file_url=_text(item, "fileUrl", "file_url"),
                    file_upload_id=_value(item, "fileUploadId", "file_upload_id"),
                    file_name=_text(item, "fileName", default="Документ"),
                    status=_text(item, "status", default="pending"),
                    points=_value(item, "points"),
                    review_comment=_text(item, "reviewComment"),
                    reviewed_by=_value(item, "reviewedBy", "reviewed_by"),
                )
            )
            counts["achievements"] += 1

        for item in raw.get("notifications", []):
            if not isinstance(item, dict):
                counts["skipped"] += 1
                continue
            notification_id = _text(item, "id")
            if not notification_id or await uow.session.get(NotificationRow, notification_id):
                counts["skipped"] += 1
                continue
            uow.session.add(
                NotificationRow(
                    id=notification_id,
                    target_type=_text(item, "targetType", "target_type", default="all"),
                    target_id=_text(item, "targetId", "target_id"),
                    kind=_text(item, "kind", default="system"),
                    title=_text(item, "title"),
                    message=_text(item, "message"),
                    email_requested=bool(_value(item, "emailRequested", default=False)),
                    created_by=_value(item, "createdBy", "created_by"),
                )
            )
            counts["notifications"] += 1

    await engine.dispose()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Frozen reference data/lug.json")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(import_state(args.input.resolve(), args.database_url)), ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
