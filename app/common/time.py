"""UTC and competition-window helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def in_window(
    settings: dict[str, object], start_key: str, end_key: str, moment: datetime | None = None
) -> bool:
    current = moment or now_utc()
    start = parse_datetime(settings.get(start_key))
    end = parse_datetime(settings.get(end_key))
    return bool(start and end and start <= current <= end)
