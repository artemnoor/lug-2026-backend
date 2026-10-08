from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import TeamRow, UserRow


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
    assert version == ("0002_captain_user_roles",)
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


def test_existing_team_captains_are_migrated_to_captain_role(tmp_path: Path) -> None:
    database = tmp_path / "captain-role-migration.db"
    initial = _alembic(tmp_path, database, "upgrade", "0001_initial_schema")
    assert initial.returncode == 0, initial.stdout + initial.stderr

    engine = create_engine(f"sqlite:///{database}")
    with Session(engine) as session:
        team = TeamRow(
            id="legacy-team",
            group="LEGACY-1",
            name="Legacy team",
            captain_id="legacy-captain",
            invite_code="LEGACY-INVITE",
            member_limit=1,
        )
        session.add(team)
        session.flush()
        session.add(
            UserRow(
                id="legacy-captain",
                email="legacy-captain@example.test",
                password_hash="test-hash",
                role="participant",
                fio="Legacy Captain",
                team_id=team.id,
            )
        )
        session.commit()
    engine.dispose()

    migrated = _alembic(tmp_path, database, "upgrade", "head")
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    with sqlite3.connect(database) as connection:
        role = connection.execute(
            "SELECT role FROM users WHERE id = ?", ("legacy-captain",)
        ).fetchone()
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert role == ("captain",)
    assert version == ("0002_captain_user_roles",)

    downgraded = _alembic(tmp_path, database, "downgrade", "0001_initial_schema")
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
    with sqlite3.connect(database) as connection:
        downgraded_role = connection.execute(
            "SELECT role FROM users WHERE id = ?", ("legacy-captain",)
        ).fetchone()
    assert downgraded_role == ("participant",)
