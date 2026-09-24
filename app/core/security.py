"""Authentication primitives and policy-independent token helpers."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

SESSION_COOKIE = "lug_session"
CSRF_COOKIE = "lug_csrf"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INVITE_RE = re.compile(r"^INV-[A-F0-9]{32}$")
_PASSWORD_HASHER = PasswordHasher()


def normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def valid_email(value: str) -> bool:
    parsed = parseaddr(value)[1]
    return len(value) <= 254 and bool(EMAIL_RE.fullmatch(value)) and parsed == value


def strong_password(value: str) -> bool:
    """Preserve the reference policy while using Argon2id as the default hash."""

    return (
        len(value) >= 8
        and bool(re.search(r"[a-z]", value))
        and bool(re.search(r"[A-Z]", value))
        and bool(re.search(r"\d", value))
        and bool(re.search(r"[^A-Za-z0-9]", value))
    )


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_PASSWORD_HASHER.hash, password)


async def verify_password(password_hash: str, password: str) -> tuple[bool, bool]:
    """Return (valid, needs_rehash); legacy scrypt remains read-only support."""

    if password_hash.startswith("scrypt$"):
        valid = await asyncio.to_thread(_verify_scrypt, password_hash, password)
        return valid, False
    try:
        valid = await asyncio.to_thread(_PASSWORD_HASHER.verify, password_hash, password)
        return valid, bool(valid and _PASSWORD_HASHER.check_needs_rehash(password_hash))
    except (VerificationError, VerifyMismatchError, InvalidHashError):
        return False, False


def _verify_scrypt(encoded: str, password: str) -> bool:
    try:
        _, salt, expected = encoded.split("$", 2)
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verification_hash(secret: str, value: str, purpose: str = "email") -> str:
    return hmac.new(f"{secret}:{purpose}".encode(), value.encode(), hashlib.sha256).hexdigest()


def issue_claim(secret: str, subject: str, key: str = "", ttl_seconds: int = 900) -> str:
    expires = int(datetime.now(timezone.utc).timestamp()) + ttl_seconds
    raw = f"{subject}|{key}|{expires}"
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{raw}|{encoded}"


def verify_claim(token: str, secret: str) -> dict[str, str] | None:
    try:
        subject, key, expires_raw, signature = token.split("|", 3)
        if int(expires_raw) < int(datetime.now(timezone.utc).timestamp()):
            return None
        raw = f"{subject}|{key}|{expires_raw}"
        expected = (
            base64.urlsafe_b64encode(
                hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
            )
            .decode()
            .rstrip("=")
        )
        if not hmac.compare_digest(signature, expected):
            return None
        return {"subject": subject, "key": key}
    except (ValueError, TypeError):
        return None


def csrf_valid(csrf_cookie: str, csrf_header: str) -> bool:
    return bool(csrf_cookie and csrf_header and hmac.compare_digest(csrf_cookie, csrf_header))


def valid_invite_code(value: str) -> bool:
    return bool(INVITE_RE.fullmatch(value))


def new_invite_code() -> str:
    return f"INV-{secrets.token_hex(16).upper()}"


def safe_public_user(user: Any) -> dict[str, Any]:
    if user is None:
        return {}
    source = (
        user
        if isinstance(user, dict)
        else {column: getattr(user, column) for column in user.__table__.columns.keys()}
    )
    keys = (
        "id",
        "email",
        "phone",
        "role",
        "team_id",
        "teamId",
        "fio",
        "identity_status",
        "identityStatus",
        "avatar_url",
        "avatarUrl",
        "student_card_file",
        "studentCardFile",
        "messenger",
        "messenger_contact",
        "messengerContact",
        "telegram_account",
        "telegramAccount",
        "email_verified",
        "emailVerified",
    )
    result = {key: source[key] for key in keys if key in source}
    if "team_id" in result and "teamId" not in result:
        result["teamId"] = result["team_id"]
    if "identity_status" in result and "identityStatus" not in result:
        result["identityStatus"] = result["identity_status"]
    if "student_card_file" in result and "studentCardFile" not in result:
        result["studentCardFile"] = result["student_card_file"]
    if "email_verified" in result and "emailVerified" not in result:
        result["emailVerified"] = result["email_verified"]
    return result
