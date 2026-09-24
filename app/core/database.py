"""Async SQLAlchemy engine, session factory, and explicit Unit of Work."""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    AsyncSessionTransaction,
    async_sessionmaker,
    create_async_engine,
)

from .config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    kwargs: dict[str, Any] = {"echo": False, "pool_pre_ping": True}
    if settings.url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = settings.pool_max_size
        kwargs["max_overflow"] = max(0, settings.pool_max_size - settings.pool_min_size)
        kwargs["connect_args"] = postgres_connect_args(settings)
    return create_async_engine(settings.url, **kwargs)


def postgres_connect_args(settings: DatabaseSettings) -> dict[str, Any]:
    """Translate the typed PostgreSQL TLS policy into asyncpg arguments."""

    if not settings.url.startswith("postgresql") or settings.ssl_mode == "disable":
        return {}
    if settings.ssl_mode == "require":
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context = ssl.create_default_context(cafile=settings.ssl_root_cert or None)
        context.check_hostname = settings.ssl_mode == "verify-full"
    return {"ssl": context}


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


class UnitOfWork:
    """One transaction boundary for an application operation."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory
        self.session: AsyncSession = factory()
        self._transaction: AsyncSessionTransaction | None = None

    async def __aenter__(self) -> "UnitOfWork":
        self._transaction = self.session.begin()
        await self._transaction.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self._transaction is not None
        try:
            await self._transaction.__aexit__(exc_type, exc_value, traceback)
        finally:
            await self.session.close()


async def ping_database(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@asynccontextmanager
async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
