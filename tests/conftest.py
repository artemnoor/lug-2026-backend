"""Deterministic SQLite application fixture for API and integration tests."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'lug.db'}"
    settings = Settings.from_env(
        {
            "LUG_ENV": "development",
            "LUG_DATABASE_URL": database_url,
            "LUG_FILE_STORAGE_PROVIDER": "local",
            "LUG_ROOT": str(tmp_path),
            "LUG_DATA_DIR": str(tmp_path / "data"),
            "LUG_UPLOAD_DIR": str(tmp_path / "uploads"),
            "LUG_ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
            "LUG_MAX_JSON_BODY": "4096",
            "LUG_ADMIN_EMAIL": "admin@lug.local",
            "LUG_ADMIN_PASSWORD": "Strong!Admin1",
        }
    )

    async def create_schema():
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_schema())
    application = create_app(settings)
    with TestClient(application, base_url="http://127.0.0.1") as test_client:
        yield test_client
