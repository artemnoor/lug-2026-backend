"""Public content/read contract."""

from __future__ import annotations

from typing import Any, Protocol


def default_settings() -> dict[str, Any]:
    return {
        "registrationStart": "2026-01-01T00:00:00+03:00",
        "registrationDeadline": "2030-12-31T23:59:59+03:00",
        "portfolioStart": "2026-01-01T00:00:00+03:00",
        "portfolioDeadline": "2030-12-31T23:59:59+03:00",
        "videoStart": "2026-01-01T00:00:00+03:00",
        "videoDeadline": "2030-12-31T23:59:59+03:00",
        "resultsStart": "2030-01-01T00:00:00+03:00",
        "resultsDeadline": "2030-12-31T23:59:59+03:00",
        "isRegistrationOpen": True,
        "minTeamPercentage": 60,
        "inviteLifetimeDays": 30,
        "content": {
            "manifestoLead": "Четыре направления конкурса",
            "manifestoNote": "Наука, общественная деятельность, спорт и творчество.",
            "registrationHeadline": "Приём заявок открыт",
        },
    }


class ContentReader(Protocol):
    async def get_settings(self) -> dict[str, Any]: ...

    async def get_results(self) -> dict[str, Any]: ...


class ContentWriter(Protocol):
    async def get_settings(self) -> dict[str, Any]: ...

    async def update_settings(self, payload: dict[str, Any], actor_id: str) -> dict[str, Any]: ...
