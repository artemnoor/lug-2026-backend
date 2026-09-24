"""Team and registration request/response contracts."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from .common import DashboardResponse, StrictModel, TeamView, UserView


class RegisterTeamRequest(StrictModel):
    fio: str = Field(max_length=200)
    group: str = Field(max_length=100)
    team_name: str = Field(default="", alias="teamName", max_length=200)
    email: str = Field(max_length=254)
    phone: str = Field(default="", max_length=32)
    messenger: str = Field(default="", max_length=32)
    messenger_contact: str = Field(default="", alias="messengerContact", max_length=128)
    messenger_contacts: dict[str, str] = Field(default_factory=dict, alias="messengerContacts")
    telegram_account: str = Field(default="", alias="telegramAccount", max_length=128)
    password: str = Field(max_length=256)
    student_card_file: str = Field(default="", alias="studentCardFile", max_length=500)
    student_card_file_name: str = Field(
        default="student-card", alias="studentCardFileName", max_length=255
    )
    student_card_upload_token: str = Field(
        default="", alias="studentCardUploadToken", max_length=1024
    )
    student_card_size: int = Field(default=0, alias="studentCardSize", ge=0, le=250 * 1024 * 1024)
    student_card_type: str = Field(default="", alias="studentCardType", max_length=160)
    total_students_in_group: int | str | None = Field(default=None, alias="totalStudentsInGroup")
    consent: bool = False
    invite_code: str = Field(default="", alias="inviteCode", max_length=80)

    @field_validator("total_students_in_group", mode="before")
    @classmethod
    def normalize_total(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        number = int(value)
        if number <= 0:
            raise ValueError("totalStudentsInGroup must be positive")
        return number


class PendingRegistrationResponse(StrictModel):
    verificationRequired: bool
    verificationId: str
    email: str
    expiresAt: str
    message: str


class VerifyEmailRequest(StrictModel):
    verification_id: str = Field(alias="verificationId", min_length=1, max_length=80)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendEmailRequest(StrictModel):
    verification_id: str = Field(alias="verificationId", min_length=1, max_length=80)


class InviteResponse(StrictModel):
    team: dict[str, str | None]


class TeamResponse(StrictModel):
    team: TeamView


class VerifyEmailResponse(StrictModel):
    user: UserView


class DashboardContract(DashboardResponse):
    """Named alias used by the route to keep the dashboard schema discoverable."""


class TeamUpdateRequest(StrictModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    flag_url: str | None = Field(default=None, alias="flagUrl", max_length=500)


class InviteRotationResponse(StrictModel):
    invite_code: str = Field(alias="inviteCode")
    invite_expires_at: str | None = Field(default=None, alias="inviteExpiresAt")
