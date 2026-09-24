"""Alembic environment using the async SQLAlchemy engine."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import DatabaseSettings
from app.core.database import postgres_connect_args
from app.db import models  # noqa: F401 - register all declarative tables
from app.db.base import Base

config = context.config
database_url = os.environ.get(
    "LUG_DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/lug.db")
)
database_settings = DatabaseSettings(
    url=database_url,
    ssl_mode=os.environ.get("LUG_DATABASE_SSL_MODE", "disable"),
    ssl_root_cert=os.environ.get("LUG_DATABASE_SSL_ROOT_CERT", ""),
)
if database_url.startswith("sqlite"):
    sqlite_path = database_url.partition("///")[2].split("?", 1)[0]
    if sqlite_path and sqlite_path != ":memory:":
        Path(sqlite_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=postgres_connect_args(database_settings),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
