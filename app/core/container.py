"""Composition container passed through FastAPI application state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .config import Settings
from .database import UnitOfWork
from .logging import JsonLogger, Metrics
from .rate_limit import RateLimiter


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    rate_limiter: RateLimiter
    logger: JsonLogger
    metrics: Metrics
    storage: Any
    email: Any
    auth: Any = None
    users: Any = None
    teams: Any = None
    media: Any = None
    portfolio: Any = None
    video: Any = None
    notifications: Any = None
    content: Any = None
    admin: Any = None
    password_reset: Any = None

    def new_uow(self) -> "UnitOfWork":
        from .database import UnitOfWork

        return UnitOfWork(self.session_factory)
