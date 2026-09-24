"""Configurable JSON logging with sensitive-field redaction."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

_SENSITIVE = {
    "password",
    "passwordhash",
    "authorization",
    "cookie",
    "token",
    "code",
    "secret",
    "dsn",
}
_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def redact(value: Any, key: str = "") -> Any:
    normalized = key.replace("_", "").replace("-", "").lower()
    if normalized in _SENSITIVE or normalized.endswith("token") or normalized.endswith("secret"):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class JsonLogger:
    def __init__(self, service: str, level: str = "INFO") -> None:
        self.service = service
        self._logger = logging.getLogger(service)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    def log(self, level: str, event: str, **fields: Any) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": level.upper(),
            "service": self.service,
            "event": event,
            **redact(fields),
        }
        self._logger.log(
            getattr(logging, level.upper(), logging.INFO),
            json.dumps(record, ensure_ascii=False, default=str),
        )

    def debug(self, event: str, **fields: Any) -> None:
        self.log("DEBUG", event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self.log("INFO", event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self.log("WARNING", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self.log("ERROR", event, **fields)


class Metrics:
    def __init__(self, service: str) -> None:
        self.service = service
        self.counters: dict[str, int] = {}
        self.request_durations: list[float] = []

    def increment(self, name: str) -> None:
        self.counters[name] = self.counters.get(name, 0) + 1

    def observe_request(self, duration_ms: float) -> None:
        self.request_durations.append(duration_ms)
        if len(self.request_durations) > 10_000:
            del self.request_durations[: len(self.request_durations) - 10_000]

    def prometheus(self) -> str:
        lines = []
        for name, value in sorted(self.counters.items()):
            lines.append(f'lug_{name.replace(".", "_")}{{service="{self.service}"}} {value}')
        count = len(self.request_durations)
        total = sum(self.request_durations)
        lines.extend(
            [
                f'lug_http_request_duration_count{{service="{self.service}"}} {count}',
                f'lug_http_request_duration_sum{{service="{self.service}"}} {total:.3f}',
            ]
        )
        return "\n".join(lines) + "\n"


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(message)s")


def new_traceparent(value: str | None) -> tuple[str, str]:
    import secrets

    match = _TRACEPARENT.fullmatch(str(value or "").lower())
    if match and set(match.group(1)) != {"0"} and set(match.group(2)) != {"0"}:
        return str(value).lower(), match.group(1)
    trace = secrets.token_hex(16)
    parent = f"00-{trace}-{secrets.token_hex(8)}-01"
    return parent, trace


def monotonic_ms() -> float:
    return time.perf_counter() * 1000
