from __future__ import annotations

import ssl

import pytest

from app.core.config import DatabaseSettings, Settings
from app.core.database import postgres_connect_args


def _production_values() -> dict[str, str]:
    return {
        "LUG_ENV": "production",
        "LUG_DATABASE_URL": "postgresql+asyncpg://lug:secret@db.example/lug",
        "LUG_DATABASE_SSL_MODE": "verify-full",
        "REDIS_URL": "redis://redis.example:6379/0",
        "LUG_OPERATIONS_TOKEN": "x" * 32,
        "LUG_ALLOWED_HOSTS": "api.example.test",
        "LUG_FILE_STORAGE_PROVIDER": "s3",
        "LUG_S3_BUCKET": "lug-private",
        "LUG_UPLOAD_SCAN_COMMAND": "clamdscan --no-summary",
        "LUG_EMAIL_MODE": "smtp",
        "LUG_EMAIL_VERIFICATION_SECRET": "s" * 32,
        "LUG_EMAIL_LOG_CODE": "false",
        "LUG_SMTP_HOST": "smtp.example.test",
    }


def test_production_rejects_default_bootstrap_credentials():
    with pytest.raises(ValueError, match="admin email"):
        Settings.from_env(_production_values())


def test_production_configuration_accepts_explicit_credentials():
    values = _production_values()
    values.update(
        {
            "LUG_ADMIN_EMAIL": "organizer@example.test",
            "LUG_ADMIN_PASSWORD": "Strong!Prod1",
        }
    )
    settings = Settings.from_env(values)
    assert settings.app.environment == "production"
    assert settings.storage.provider == "s3"


def test_postgres_tls_policy_reaches_asyncpg_connect_args():
    disabled = DatabaseSettings(
        url="postgresql+asyncpg://lug:secret@db.example/lug", ssl_mode="disable"
    )
    assert postgres_connect_args(disabled) == {}

    verified = DatabaseSettings(
        url="postgresql+asyncpg://lug:secret@db.example/lug", ssl_mode="verify-full"
    )
    context = postgres_connect_args(verified)["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
