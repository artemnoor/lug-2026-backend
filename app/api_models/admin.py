"""Admin HTTP contracts."""

from typing import Any

from pydantic import Field

from .common import (
    AchievementView,
    NotificationView,
    SettingsView,
    StrictModel,
    TeamView,
    UserView,
    VideoCard,
)


class QuotaRequest(StrictModel):
    confirmed: bool = False


class ReviewRequest(StrictModel):
    field: str = Field(default="", max_length=32)
    status: str = Field(default="", max_length=32)
    comment: str = Field(default="", max_length=2000)
    points: float | None = Field(default=None, ge=0, le=100)
    review_stage: str = Field(default="received", alias="reviewStage", max_length=32)
    criteria_scores: dict[str, float] = Field(default_factory=dict, alias="criteriaScores")


class BroadcastRequest(StrictModel):
    target_type: str = Field(default="all", alias="targetType", max_length=32)
    target_id: str = Field(default="", alias="targetId", max_length=80)
    title: str = Field(max_length=120)
    message: str = Field(max_length=1000)
    kind: str | None = Field(default=None, max_length=32)


class AdminOverviewResponse(StrictModel):
    settings: SettingsView
    summary: dict[str, int]
    teams: list[dict[str, Any]]
    users: list[UserView]
    achievements: list[AchievementView]
    videos: list[dict[str, Any]]
    notifications: list[NotificationView]
    admin_notifications: list[NotificationView] = Field(alias="adminNotifications")
    audit_log: list[dict[str, Any]] = Field(alias="auditLog")


class CollectionResponse(StrictModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class AuditLogItem(StrictModel):
    id: str
    actor_user_id: str | None = Field(default=None, alias="actorUserId")
    action: str
    entity_type: str = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")
    payload: dict[str, Any] = Field(default_factory=dict)
    at: str


class AuditResponse(StrictModel):
    audit_log: list[AuditLogItem] = Field(alias="auditLog")


class TeamMutationResponse(StrictModel):
    team: TeamView


class UserMutationResponse(StrictModel):
    user: UserView


class AchievementMutationResponse(StrictModel):
    achievement: AchievementView


class VideoMutationResponse(StrictModel):
    video_card: VideoCard = Field(alias="videoCard")


class SettingsResponse(StrictModel):
    settings: SettingsView


class BroadcastResponse(StrictModel):
    success: bool
    email_recipients: int = Field(alias="emailRecipients")
    email_sent: int = Field(alias="emailSent")
    email_failed: int = Field(alias="emailFailed")
    email_mode: str = Field(alias="emailMode")
