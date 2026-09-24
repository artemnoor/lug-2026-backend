"""Static import rules for the vertical modular monolith."""

from __future__ import annotations

from pathlib import Path


def test_domain_and_contracts_do_not_import_framework_or_infrastructure():
    root = Path(__file__).parents[1] / "app" / "modules"
    forbidden = ("fastapi", "sqlalchemy", "redis", "boto3", "os.getenv", "from ..infrastructure")
    violations = []
    for path in root.glob("*/domain.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            if token in text:
                violations.append(f"{path}: {token}")
    assert not violations, "\n".join(violations)


def test_api_and_application_modules_do_not_leak_persistence_adapters():
    root = Path(__file__).parents[1] / "app" / "modules"
    paths = [*root.glob("*/api.py"), *root.glob("*/application.py")]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "db.models" not in text, path
        assert "from .infrastructure" not in text, path
        assert "from ..infrastructure" not in text, path
