"""Pure team and registration rules."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from ...common.time import in_window
from ...core.errors import AuthorizationError, ValidationAppError
from ...core.security import (
    new_invite_code,
    normalize_email,
    strong_password,
    valid_email,
    valid_invite_code,
)


def registration_open(settings: dict[str, Any]) -> bool:
    return settings.get("isRegistrationOpen") is True and in_window(
        settings, "registrationStart", "registrationDeadline"
    )


def portfolio_open(settings: dict[str, Any]) -> bool:
    return in_window(settings, "portfolioStart", "portfolioDeadline")


def video_open(settings: dict[str, Any]) -> bool:
    return in_window(settings, "videoStart", "videoDeadline")


def validate_registration(values: dict[str, Any], is_team: bool) -> dict[str, Any]:
    required = (
        ("fio", "group", "teamName", "email", "password", "studentCardFile")
        if is_team
        else ("fio", "email", "password", "studentCardFile")
    )
    if (
        any(not str(values.get(field) or "").strip() for field in required)
        or values.get("consent") is not True
    ):
        raise ValidationAppError(
            "Заполните все обязательные поля и подтвердите согласие.", "REQUIRED_FIELDS_INVALID"
        )
    email = normalize_email(values.get("email"))
    if not valid_email(email):
        raise ValidationAppError("Укажите корректный адрес электронной почты.", "EMAIL_INVALID")
    if not strong_password(str(values.get("password"))):
        raise ValidationAppError(
            "Пароль должен содержать минимум 8 символов, строчную и прописную букву, цифру и спецсимвол.",
            "PASSWORD_INVALID",
        )
    contacts = normalize_contacts(values)
    if not contacts:
        raise ValidationAppError(
            "Выберите хотя бы один мессенджер и укажите корректный контакт.", "CONTACTS_INVALID"
        )
    if is_team:
        total = int(values.get("totalStudentsInGroup") or 0)
        if total < 1 or total > 1000:
            raise ValidationAppError(
                "Укажите количество студентов в группе от 1 до 1000.", "TEAM_SIZE_INVALID"
            )
    values = dict(values)
    values["email"] = email
    values["messengerContacts"] = contacts
    return values


def normalize_contacts(values: dict[str, Any]) -> dict[str, str]:
    contacts: dict[str, str] = {}
    raw = values.get("messengerContacts")
    if isinstance(raw, dict):
        for key, value in raw.items():
            normalized = {"вконтакте": "vk", "telegram": "telegram", "vk": "vk", "max": "max"}.get(
                str(key).strip().lower()
            )
            if normalized and str(value or "").strip():
                contacts[normalized] = str(value).strip()
    legacy = str(values.get("messenger") or "").strip().lower()
    if legacy in {"telegram", "vk", "max"} and str(values.get("messengerContact") or "").strip():
        contacts.setdefault(legacy, str(values["messengerContact"]).strip())
    if str(values.get("telegramAccount") or "").strip():
        contacts.setdefault("telegram", str(values["telegramAccount"]).strip())
    return contacts


def check_captain(team: dict[str, Any], user: dict[str, Any]) -> None:
    if team.get("captainId") != user.get("id"):
        raise AuthorizationError(
            "Изменять данные команды может только капитан.", "CAPTAIN_REQUIRED"
        )


def quota(team: Any, member_count: int, percentage: int) -> dict[str, Any]:
    required = math.ceil(int(team.member_limit) * int(percentage) / 100)
    eligible = member_count >= required
    return {
        "members": member_count,
        "required": required,
        "total": int(team.member_limit),
        "percentage": percentage,
        "eligible": eligible,
    }


def is_admitted(team: Any, members: list[Any], percentage: int) -> bool:
    """Compute admission from persisted review state instead of a stale flag."""

    review_fields = (
        "review_name_status",
        "review_group_status",
        "review_flag_status",
        "review_description_status",
    )
    return bool(
        team.quota_confirmed
        and quota(team, len(members), percentage)["eligible"]
        and members
        and all(member.identity_status == "approved" for member in members)
        and all(getattr(team, field) == "approved" for field in review_fields)
    )


def new_team_data(
    group: str, name: str, member_limit: int, invite_lifetime_days: int
) -> dict[str, Any]:
    from datetime import timedelta, timezone

    now = datetime.now(timezone.utc)
    return {
        "group": group.strip().upper(),
        "name": name.strip(),
        "invite_code": new_invite_code(),
        "invite_expires_at": now + timedelta(days=invite_lifetime_days),
        "member_limit": member_limit,
    }


def check_invite(code: str) -> str:
    normalized = str(code or "").strip().upper()
    if not valid_invite_code(normalized):
        raise ValidationAppError("Приглашение не найдено, отозвано или истекло.", "INVITE_INVALID")
    return normalized
