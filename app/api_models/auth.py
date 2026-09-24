"""Authentication HTTP contracts."""

from __future__ import annotations

from pydantic import Field

from .common import SessionView, StrictModel, UserView


class LoginRequest(StrictModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(StrictModel):
    user: UserView


class SessionResponse(StrictModel):
    user: UserView | None


class SessionListResponse(StrictModel):
    sessions: list[SessionView]


class RemoveSessionsResponse(StrictModel):
    removed: int


class PasswordResetRequest(StrictModel):
    email: str = Field(max_length=254)


class PasswordResetConfirm(StrictModel):
    email: str = Field(max_length=254)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    password: str = Field(max_length=256)
