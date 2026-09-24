from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_legacy_json_import_preserves_core_entities(tmp_path: Path) -> None:
    database = tmp_path / "import.db"
    environment = os.environ.copy()
    database_url = f"sqlite+aiosqlite:///{database.as_posix()}"
    environment["LUG_DATABASE_URL"] = database_url

    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr

    imported = subprocess.run(
        [
            sys.executable,
            "scripts/import_legacy_json.py",
            str(ROOT / "tests" / "fixtures" / "legacy-small.json"),
            "--database-url",
            database_url,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stdout + imported.stderr
    counts = json.loads(imported.stdout)
    assert counts["teams"] == 1
    assert counts["users"] == 1
    assert counts["achievements"] == 1
    assert counts["notifications"] == 1

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM teams").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM users").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM achievements").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM notifications").fetchone() == (1,)
