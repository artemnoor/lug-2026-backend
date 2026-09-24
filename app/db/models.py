"""Explicit persistence rows for the LUG competition domains.

The model deliberately keeps core fields relational. JSON columns are limited to
extensible review criteria/content and are never the only source for identity,
ownership, status, or authorization data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class SettingRow(Base, TimestampMixin):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class UserRow(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="participant")
    fio: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    messenger: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    messenger_contact: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    telegram_account: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    team_id: Mapped[str | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    identity_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    identity_comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    student_card_file: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    team: Mapped["TeamRow | None"] = relationship(
        "TeamRow", foreign_keys=[team_id], back_populates="members"
    )
    achievements: Mapped[list["AchievementRow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["SessionRow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_users_email_lower", "email"),
        Index("ix_users_identity_status", "identity_status"),
    )


class TeamRow(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    captain_id: Mapped[str | None] = mapped_column(String(64), index=True)
    invite_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    invite_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    member_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    flag_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    quota_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_name_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    review_group_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    review_flag_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    review_description_status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    review_comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    video_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    video_file_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    video_status: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    video_comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    video_score: Mapped[float | None] = mapped_column()
    video_criteria_scores: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    members: Mapped[list[UserRow]] = relationship(
        "UserRow", foreign_keys=[UserRow.team_id], back_populates="team"
    )

    __table_args__ = (
        Index("ix_teams_invite", "invite_code", "invite_status"),
        Index("ix_teams_review", "review_name_status", "review_group_status", "review_flag_status"),
    )


class UploadRow(Base, TimestampMixin):
    __tablename__ = "uploads"

    upload_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    claim_subject: Mapped[str | None] = mapped_column(String(128), index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    storage_path: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    scan_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    scan_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)

    owner: Mapped[UserRow | None] = relationship("UserRow", foreign_keys=[owner_user_id])

    __table_args__ = (
        Index("ix_uploads_owner_status", "owner_user_id", "status", "scan_status"),
        Index("ix_uploads_claim", "claim_subject", "created_at"),
    )


class AchievementRow(Base, TimestampMixin):
    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    file_upload_id: Mapped[str | None] = mapped_column(
        ForeignKey("uploads.upload_id", ondelete="SET NULL")
    )
    file_name: Mapped[str] = mapped_column(String(255), default="Документ", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    points: Mapped[float | None] = mapped_column()
    review_comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[UserRow] = relationship(back_populates="achievements")
    upload: Mapped[UploadRow | None] = relationship("UploadRow")

    __table_args__ = (Index("ix_achievements_status", "status", "updated_at"),)


class NotificationRow(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(4000), nullable=False)
    email_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64))

    reads: Mapped[list["NotificationReadRow"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )
    __table_args__ = (
        Index("ix_notifications_target_time", "target_type", "target_id", "created_at"),
    )


class NotificationReadRow(Base):
    __tablename__ = "notification_reads"

    notification_id: Mapped[str] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    notification: Mapped[NotificationRow] = relationship(back_populates="reads")


class SessionRow(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    user_agent: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    user: Mapped[UserRow] = relationship(back_populates="sessions")


class EmailVerificationRow(Base, TimestampMixin):
    __tablename__ = "email_verifications"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="registration")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("email", "purpose", name="uq_email_verifications_email_purpose"),
    )


class PasswordResetRow(Base, TimestampMixin):
    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
