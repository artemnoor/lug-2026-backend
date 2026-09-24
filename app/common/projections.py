"""Mapping between ORM rows/domain DTOs and the legacy frontend projection."""

from __future__ import annotations

from typing import Any


def user_view(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "id": row.id,
        "email": row.email,
        "phone": row.phone or "",
        "role": row.role,
        "teamId": row.team_id,
        "fio": row.fio,
        "messenger": row.messenger,
        "messengerContact": row.messenger_contact,
        "telegramAccount": row.telegram_account,
        "identityStatus": row.identity_status,
        "identityComment": row.identity_comment,
        "avatarUrl": row.avatar_url,
        "studentCardFile": row.student_card_file,
        "emailVerified": row.email_verified,
    }


def team_view(row: Any, members: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "id": row.id,
        "group": row.group,
        "name": row.name,
        "description": row.description,
        "captainId": row.captain_id,
        "inviteCode": row.invite_code,
        "inviteStatus": row.invite_status,
        "inviteExpiresAt": row.invite_expires_at.isoformat() if row.invite_expires_at else None,
        "memberLimit": row.member_limit,
        "flagUrl": row.flag_url,
        "quotaConfirmed": row.quota_confirmed,
        "isQuotaConfirmed": row.quota_confirmed,
        "isAdmitted": row.is_admitted,
        "videoCard": video_view(row),
        "members": members or [],
    }


def video_view(row: Any) -> dict[str, Any]:
    return {
        "url": row.video_url or "",
        "fileUrl": row.video_file_url or "",
        "status": row.video_status or "none",
        "comment": row.video_comment or "",
        "score": row.video_score,
        "criteriaScores": row.video_criteria_scores or {},
    }


def achievement_view(row: Any, owner: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "userId": row.user_id,
        "title": row.title,
        "direction": row.direction,
        "category": row.category,
        "details": row.details,
        "fileUrl": row.file_url,
        "fileName": row.file_name,
        "status": row.status,
        "points": row.points,
        "reviewComment": row.review_comment,
        "user": owner,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def notification_view(row: Any, read: bool = False) -> dict[str, Any]:
    return {
        "id": row.id,
        "targetType": row.target_type,
        "targetId": row.target_id,
        "kind": row.kind,
        "title": row.title,
        "message": row.message,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "read": read,
    }


def upload_view(row: Any) -> dict[str, Any]:
    return {
        "upload_id": row.upload_id,
        "uploadId": row.upload_id,
        "url": row.url,
        "storage_key": row.storage_key,
        "storage_path": row.storage_path,
        "original_name": row.original_name,
        "name": row.original_name,
        "content_type": row.content_type,
        "contentType": row.content_type,
        "size_bytes": row.size_bytes,
        "size": row.size_bytes,
        "kind": row.kind,
        "status": row.status,
        "scan_status": row.scan_status,
        "owner_user_id": row.owner_user_id,
        "claim_subject": row.claim_subject,
    }


def settings_view(data: dict[str, Any]) -> dict[str, Any]:
    return dict(data)
