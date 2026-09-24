"""Profile update contract."""

from __future__ import annotations

from pydantic import Field

from .common import StrictModel, UserView


class UpdateProfileRequest(StrictModel):
    fio: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    messenger: str | None = Field(default=None, max_length=32)
    messenger_contact: str | None = Field(default=None, alias="messengerContact", max_length=128)
    messenger_contacts: dict[str, str] | None = Field(default=None, alias="messengerContacts")
    telegram_account: str | None = Field(default=None, alias="telegramAccount", max_length=128)
    avatar_url: str | None = Field(default=None, alias="avatarUrl", max_length=500)
    student_card_file: str | None = Field(default=None, alias="studentCardFile", max_length=500)
    student_card_file_name: str | None = Field(
        default=None, alias="studentCardFileName", max_length=255
    )


class UserResponse(StrictModel):
    user: UserView
