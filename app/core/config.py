"""Typed configuration loaded once at the composition boundary.

No module below ``core.config`` reads process environment variables directly.
The settings object is deliberately explicit instead of relying on a global
service locator so tests can inject a complete configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = "lug-api"
    environment: str = "development"
    build_version: str = "dev"
    build_sha: str = "unknown"
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    log_level: str = "INFO"


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str = "sqlite+aiosqlite:///./data/lug.db"
    pool_min_size: int = Field(default=2, ge=1, le=100)
    pool_max_size: int = Field(default=20, ge=1, le=200)
    ssl_mode: str = "disable"
    ssl_root_cert: str = ""
    redis_url: str = ""

    @field_validator("ssl_mode")
    @classmethod
    def validate_ssl_mode(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"disable", "require", "verify-ca", "verify-full"}:
            raise ValueError(
                "database ssl_mode must be disable, require, verify-ca, or verify-full"
            )
        return value


class SecuritySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    operations_token: str = ""
    trust_proxy: bool = False
    trusted_proxy_ips: tuple[str, ...] = ()
    secure_cookies: bool = False
    session_ttl_seconds: int = Field(default=604800, ge=300, le=2_592_000)
    max_json_body: int = Field(default=2 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    max_upload_body: int = Field(default=70 * 1024 * 1024, ge=1024, le=500 * 1024 * 1024)
    admin_email: str = "admin@lug.local"
    admin_password: str = "Strong!Admin1"


class StorageSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = "local"
    data_dir: Path = Path("./data")
    upload_dir: Path = Path("./uploads")
    upload_scan_command: str = ""
    upload_scan_required: bool = False
    max_upload_bytes: int = Field(default=250 * 1024 * 1024, ge=1, le=2 * 1024 * 1024 * 1024)
    max_uploads_per_user: int = Field(default=50, ge=1, le=10_000)
    max_upload_bytes_per_user: int = Field(default=250 * 1024 * 1024, ge=1)
    upload_rate_limit_per_ip: int = Field(default=30, ge=1)
    upload_rate_limit_per_user: int = Field(default=30, ge=1)
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_prefix: str = "uploads"
    s3_signed_url_ttl: int = Field(default=300, ge=60, le=3600)
    s3_server_side_encryption: str = "AES256"
    s3_kms_key_id: str = ""


class EmailSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str = "log"
    verification_secret: str = "local-development-email-secret"
    verification_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    verification_cooldown_seconds: int = Field(default=60, ge=10, le=3600)
    verification_max_attempts: int = Field(default=5, ge=1, le=20)
    log_code: bool = True
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65_535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@lug.local"
    smtp_from_name: str = "LUG 2026"
    smtp_starttls: bool = True
    smtp_ssl: bool = False


class Settings(BaseModel):
    """Complete application configuration and production validation."""

    model_config = ConfigDict(frozen=True)

    root_dir: Path = Path(__file__).resolve().parents[2]
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> "Settings":
        if values is None:
            process_env = dict(os.environ)
            root_candidate = Path(
                process_env.get("LUG_ROOT", str(Path(__file__).resolve().parents[2]))
            ).resolve()
            file_env = {
                key: value
                for key, value in dotenv_values(root_candidate / ".env").items()
                if value is not None
            }
            env = {**file_env, **process_env}
        else:
            env = dict(values)
        environment = env.get("LUG_ENV", env.get("NODE_ENV", "development")).strip().lower()
        root_dir = Path(env.get("LUG_ROOT", str(Path(__file__).resolve().parents[2]))).resolve()
        allowed_hosts = _csv(env.get("LUG_ALLOWED_HOSTS", "127.0.0.1,localhost"))
        database_url = env.get("LUG_DATABASE_URL", env.get("DATABASE_URL", "")).strip()
        if not database_url:
            database_url = "sqlite+aiosqlite:///./data/lug.db"
        provider = env.get(
            "LUG_FILE_STORAGE_PROVIDER", "s3" if environment == "production" else "local"
        )
        settings = cls(
            root_dir=root_dir,
            app=AppSettings(
                name=env.get("LUG_APP_NAME", "lug-api"),
                environment=environment,
                build_version=env.get("LUG_BUILD_VERSION", "dev"),
                build_sha=env.get("LUG_BUILD_SHA", "unknown"),
                allowed_hosts=allowed_hosts,
                log_level=env.get("LOG_LEVEL", "INFO").upper(),
            ),
            database=DatabaseSettings(
                url=database_url,
                pool_min_size=_int(env, "LUG_DATABASE_POOL_MIN_SIZE", 2),
                pool_max_size=_int(env, "LUG_DATABASE_POOL_MAX_SIZE", 20),
                ssl_mode=env.get("LUG_DATABASE_SSL_MODE", "disable"),
                ssl_root_cert=env.get("LUG_DATABASE_SSL_ROOT_CERT", "").strip(),
                redis_url=env.get("REDIS_URL", "").strip(),
            ),
            security=SecuritySettings(
                allowed_hosts=allowed_hosts,
                operations_token=env.get("LUG_OPERATIONS_TOKEN", "").strip(),
                trust_proxy=_bool(env, "LUG_TRUST_PROXY", False),
                trusted_proxy_ips=_csv(env.get("LUG_TRUSTED_PROXY_IPS", "")),
                secure_cookies=_bool(
                    env, "LUG_SECURE_COOKIES", environment in {"staging", "production"}
                ),
                session_ttl_seconds=_int(env, "LUG_SESSION_TTL_SECONDS", 604800),
                max_json_body=_int(env, "LUG_MAX_JSON_BODY", 2 * 1024 * 1024),
                max_upload_body=_int(env, "LUG_MAX_UPLOAD_BODY", 70 * 1024 * 1024),
                admin_email=env.get("LUG_ADMIN_EMAIL", "admin@lug.local"),
                admin_password=env.get("LUG_ADMIN_PASSWORD", "Strong!Admin1"),
            ),
            storage=StorageSettings(
                provider=provider,
                data_dir=_path(env.get("LUG_DATA_DIR", str(root_dir / "data")), root_dir),
                upload_dir=_path(env.get("LUG_UPLOAD_DIR", str(root_dir / "uploads")), root_dir),
                upload_scan_command=env.get("LUG_UPLOAD_SCAN_COMMAND", "").strip(),
                upload_scan_required=_bool(
                    env, "LUG_UPLOAD_SCAN_REQUIRED", environment == "production"
                ),
                max_upload_bytes=_int(env, "LUG_MAX_UPLOAD_BYTES", 250 * 1024 * 1024),
                max_uploads_per_user=_int(env, "LUG_MAX_UPLOADS_PER_USER", 50),
                max_upload_bytes_per_user=_int(
                    env, "LUG_MAX_UPLOAD_BYTES_PER_USER", 250 * 1024 * 1024
                ),
                upload_rate_limit_per_ip=_int(env, "LUG_UPLOAD_RATE_LIMIT_PER_IP", 30),
                upload_rate_limit_per_user=_int(env, "LUG_UPLOAD_RATE_LIMIT_PER_USER", 30),
                s3_bucket=env.get("LUG_S3_BUCKET", "").strip(),
                s3_region=env.get("LUG_S3_REGION", "").strip(),
                s3_endpoint_url=env.get("LUG_S3_ENDPOINT_URL", "").strip(),
                s3_access_key=env.get("LUG_S3_ACCESS_KEY", "").strip(),
                s3_secret_key=env.get("LUG_S3_SECRET_KEY", ""),
                s3_prefix=env.get("LUG_S3_PREFIX", "uploads").strip("/") or "uploads",
                s3_signed_url_ttl=_int(env, "LUG_S3_SIGNED_URL_TTL", 300),
                s3_server_side_encryption=env.get("LUG_S3_SERVER_SIDE_ENCRYPTION", "AES256"),
                s3_kms_key_id=env.get("LUG_S3_KMS_KEY_ID", "").strip(),
            ),
            email=EmailSettings(
                mode=env.get(
                    "LUG_EMAIL_MODE", "smtp" if environment in {"staging", "production"} else "log"
                ),
                verification_secret=env.get(
                    "LUG_EMAIL_VERIFICATION_SECRET", "local-development-email-secret"
                ),
                verification_ttl_seconds=_int(env, "LUG_EMAIL_VERIFICATION_TTL_SECONDS", 900),
                verification_cooldown_seconds=_int(
                    env, "LUG_EMAIL_VERIFICATION_COOLDOWN_SECONDS", 60
                ),
                verification_max_attempts=_int(env, "LUG_EMAIL_VERIFICATION_MAX_ATTEMPTS", 5),
                log_code=_bool(
                    env, "LUG_EMAIL_LOG_CODE", environment not in {"staging", "production"}
                ),
                smtp_host=env.get("LUG_SMTP_HOST", "").strip(),
                smtp_port=_int(env, "LUG_SMTP_PORT", 587),
                smtp_user=env.get("LUG_SMTP_USER", "").strip(),
                smtp_password=env.get("LUG_SMTP_PASSWORD", ""),
                smtp_from=env.get("LUG_SMTP_FROM", "no-reply@lug.local").strip(),
                smtp_from_name=env.get("LUG_SMTP_FROM_NAME", "LUG 2026").strip(),
                smtp_starttls=_bool(env, "LUG_SMTP_STARTTLS", True),
                smtp_ssl=_bool(env, "LUG_SMTP_SSL", False),
            ),
        )
        settings.validate_runtime()
        return settings

    def validate_runtime(self) -> None:
        env = self.app.environment
        if env in {"staging", "production"}:
            if self.database.url.startswith("sqlite") or self.database.ssl_mode != "verify-full":
                raise ValueError("staging/production requires PostgreSQL with verify-full SSL")
            if not self.database.redis_url:
                raise ValueError("staging/production requires REDIS_URL")
            if len(self.security.operations_token) < 32:
                raise ValueError("staging/production requires a 32-character operations token")
            if self.security.admin_email == "admin@lug.local":
                raise ValueError("staging/production requires an explicit admin email")
            if self.security.admin_password == "Strong!Admin1":
                raise ValueError("staging/production requires an explicit admin password")
            if not self.security.allowed_hosts or any(
                "*" in item for item in self.security.allowed_hosts
            ):
                raise ValueError("staging/production requires explicit allowed hosts")
            if self.storage.provider != "s3" or not self.storage.s3_bucket:
                raise ValueError("production requires configured private S3 storage")
            if self.storage.upload_scan_required and not self.storage.upload_scan_command:
                raise ValueError("production requires a configured upload scanner command")
            if self.email.mode != "smtp" or len(self.email.verification_secret) < 32:
                raise ValueError("staging/production requires SMTP and a 32-character email secret")
            if not self.email.smtp_host:
                raise ValueError("staging/production requires an SMTP host")
            if self.email.log_code:
                raise ValueError("verification codes must not be logged in staging/production")
        if self.storage.provider not in {"local", "s3"}:
            raise ValueError("LUG_FILE_STORAGE_PROVIDER must be local or s3")
        if self.storage.provider == "s3" and not self.storage.s3_bucket:
            raise ValueError("S3 storage requires LUG_S3_BUCKET")
        if bool(self.storage.s3_access_key) != bool(self.storage.s3_secret_key):
            raise ValueError("S3 access and secret keys must be provided together")
        if self.storage.s3_server_side_encryption not in {"AES256", "aws:kms"}:
            raise ValueError("unsupported S3 server-side encryption")
        if self.storage.s3_server_side_encryption == "aws:kms" and not self.storage.s3_kms_key_id:
            raise ValueError("aws:kms storage requires LUG_S3_KMS_KEY_ID")


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip().lower().rstrip(".") for item in value.split(",") if item.strip())


def _int(values: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(values.get(key, str(default)))
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc


def _bool(values: Mapping[str, str], key: str, default: bool) -> bool:
    raw = values.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _path(value: str, root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()
