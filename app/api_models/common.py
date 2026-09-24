"""Shared request/response schemas used in OpenAPI."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ErrorBody(StrictModel):
    error: str
    code: str
    details: Any | None = None


class HealthResponse(StrictModel):
    status: str
    service: str
    version: str | None = None


class ReadinessResponse(StrictModel):
    status: str
    service: str
    dependencies: dict[str, bool] | None = None


class VersionResponse(StrictModel):
    service: str
    version: str
    sha: str


class UserView(StrictModel):
    id: str
    email: str
    phone: str = ""
    role: str
    team_id: str | None = Field(default=None, alias="teamId")
    fio: str = ""
    messenger: str = ""
    messenger_contact: str = Field(default="", alias="messengerContact")
    telegram_account: str = Field(default="", alias="telegramAccount")
    identity_status: str = Field(default="pending", alias="identityStatus")
    identity_comment: str = Field(default="", alias="identityComment")
    avatar_url: str = Field(default="", alias="avatarUrl")
    student_card_file: str = Field(default="", alias="studentCardFile")
    email_verified: bool = Field(default=False, alias="emailVerified")


class VideoCard(StrictModel):
    url: str = ""
    file_url: str = Field(default="", alias="fileUrl")
    status: str = "none"
    comment: str = ""
    score: float | None = None
    criteria_scores: dict[str, float] = Field(default_factory=dict, alias="criteriaScores")


class TeamView(StrictModel):
    id: str
    group: str
    name: str
    description: str = ""
    captain_id: str | None = Field(default=None, alias="captainId")
    invite_code: str = Field(default="", alias="inviteCode")
    invite_status: str = Field(default="active", alias="inviteStatus")
    invite_expires_at: str | None = Field(default=None, alias="inviteExpiresAt")
    member_limit: int = Field(default=1, alias="memberLimit")
    flag_url: str = Field(default="", alias="flagUrl")
    quota_confirmed: bool = Field(default=False, alias="quotaConfirmed")
    is_quota_confirmed: bool = Field(default=False, alias="isQuotaConfirmed")
    is_admitted: bool = Field(default=False, alias="isAdmitted")
    video_card: VideoCard = Field(default_factory=VideoCard, alias="videoCard")
    members: list[UserView] = Field(default_factory=list)


class AchievementView(StrictModel):
    id: str
    user_id: str = Field(alias="userId")
    title: str
    direction: str
    category: str
    details: str = ""
    file_url: str = Field(default="", alias="fileUrl")
    file_name: str = Field(default="Документ", alias="fileName")
    status: str = "pending"
    points: float | None = None
    review_comment: str = Field(default="", alias="reviewComment")
    user: UserView | None = None
    created_at: str | None = Field(default=None, alias="createdAt")


class NotificationView(StrictModel):
    id: str
    target_type: str = Field(alias="targetType")
    target_id: str = Field(default="", alias="targetId")
    kind: str
    title: str
    message: str
    created_at: str | None = Field(default=None, alias="createdAt")
    read: bool = False


class SettingsView(StrictModel):
    registration_start: str = Field(alias="registrationStart")
    registration_deadline: str = Field(alias="registrationDeadline")
    portfolio_start: str = Field(alias="portfolioStart")
    portfolio_deadline: str = Field(alias="portfolioDeadline")
    video_start: str = Field(alias="videoStart")
    video_deadline: str = Field(alias="videoDeadline")
    results_start: str = Field(alias="resultsStart")
    results_deadline: str = Field(alias="resultsDeadline")
    is_registration_open: bool = Field(alias="isRegistrationOpen")
    min_team_percentage: int = Field(alias="minTeamPercentage")
    invite_lifetime_days: int = Field(alias="inviteLifetimeDays")
    content: dict[str, Any] = Field(default_factory=dict)


class ResultTeam(StrictModel):
    id: str
    name: str
    group: str
    score: float
    admitted: bool


class DashboardResponse(StrictModel):
    user: UserView
    team: TeamView | None = None
    members: list[UserView] = Field(default_factory=list)
    achievements: list[AchievementView] = Field(default_factory=list)
    notifications: list[NotificationView] = Field(default_factory=list)
    settings: SettingsView


class SessionView(StrictModel):
    id: str
    created_at: str = Field(alias="createdAt")
    expires_at: str = Field(alias="expiresAt")
    user_agent: str = Field(default="", alias="userAgent")
    ip_address: str = Field(default="", alias="ipAddress")


class PaginationQuery(StrictModel):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SuccessResponse(StrictModel):
    success: bool = True
