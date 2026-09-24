"""Public content and admin settings contracts."""

from typing import Any

from .common import ResultTeam, SettingsView, StrictModel


class ConfigResponse(StrictModel):
    settings: SettingsView


class ResultsResponse(StrictModel):
    published: bool
    availableFrom: str | None = None
    teams: list[ResultTeam]


class SettingsUpdateRequest(StrictModel):
    registrationStart: str | None = None
    registrationDeadline: str | None = None
    portfolioStart: str | None = None
    portfolioDeadline: str | None = None
    videoStart: str | None = None
    videoDeadline: str | None = None
    resultsStart: str | None = None
    resultsDeadline: str | None = None
    isRegistrationOpen: bool | None = None
    minTeamPercentage: int | None = None
    inviteLifetimeDays: int | None = None
    content: dict[str, Any] | None = None
