from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _alembic(tmp_path: Path, database: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["LUG_DATABASE_URL"] = f"sqlite+aiosqlite:///{database.as_posix()}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_clean_database_can_upgrade_and_downgrade(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"

    upgraded = _alembic(tmp_path, database, "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr

    with sqlite3.connect(database) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert version == ("0001_initial_schema",)
    assert {
        "users",
        "teams",
        "uploads",
        "achievements",
        "notifications",
        "sessions",
        "email_verifications",
        "password_resets",
        "audit_log",
    }.issubset(tables)

    downgraded = _alembic(tmp_path, database, "downgrade", "base")
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr

    upgraded_again = _alembic(tmp_path, database, "upgrade", "head")
    assert upgraded_again.returncode == 0, upgraded_again.stdout + upgraded_again.stderr
