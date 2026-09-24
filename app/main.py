"""FastAPI composition root for the rebuilt LUG backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .core.config import Settings
from .core.container import AppContainer
from .core.database import UnitOfWork, create_engine, create_session_factory
from .core.http import install_http
from .core.logging import JsonLogger, Metrics, configure_logging
from .core.operations import router as operations_router
from .core.rate_limit import create_rate_limiter
from .infrastructure.email import EmailService
from .infrastructure.scanner import build_scanner
from .infrastructure.storage import build_storage
from .modules.admin.api import router as admin_router
from .modules.admin.application import AdminService
from .modules.admin.infrastructure import SqlAlchemyAdminRepository
from .modules.auth.api import router as auth_router
from .modules.auth.application import AuthService
from .modules.auth.infrastructure import SqlAlchemyAuthRepository
from .modules.auth.password import PasswordResetService
from .modules.auth.password_api import router as password_router
from .modules.content.api import router as content_router
from .modules.content.application import ContentService
from .modules.content.infrastructure import SqlAlchemyContentRepository
from .modules.media.api import router as media_router
from .modules.media.application import MediaService
from .modules.media.infrastructure import SqlAlchemyMediaRepository
from .modules.notifications.api import router as notifications_router
from .modules.notifications.application import NotificationService
from .modules.notifications.infrastructure import SqlAlchemyNotificationRepository
from .modules.portfolio.api import router as portfolio_router
from .modules.portfolio.application import PortfolioService
from .modules.portfolio.infrastructure import SqlAlchemyPortfolioRepository
from .modules.teams.api import router as teams_router
from .modules.teams.application import TeamService
from .modules.teams.infrastructure import SqlAlchemyTeamRepository
from .modules.users.api import router as users_router
from .modules.users.application import UserService
from .modules.users.infrastructure import SqlAlchemyUserRepository
from .modules.video.api import router as video_router
from .modules.video.application import VideoService
from .modules.video.infrastructure import SqlAlchemyVideoRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    http_logger = JsonLogger(resolved.app.name, resolved.app.log_level)
    http_metrics = Metrics(resolved.app.name)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging(resolved.app.log_level)
        logger = http_logger
        metrics = http_metrics
        engine = create_engine(resolved.database)
        session_factory = create_session_factory(engine)
        limiter = await create_rate_limiter(resolved.database.redis_url)
        storage_redis = None
        if resolved.database.redis_url:
            from redis.asyncio import Redis

            storage_redis = Redis.from_url(
                resolved.database.redis_url,
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
        scanner = build_scanner(resolved.storage, logger)
        storage = build_storage(resolved.storage, logger, storage_redis, scanner)
        email = EmailService(resolved.email, logger)

        # Build domain applications after the low-level adapters. Cross-module
        # references are public application contracts, never ORM internals.
        def uow_factory() -> UnitOfWork:
            return UnitOfWork(session_factory)

        auth = AuthService(uow_factory, resolved.security, logger, SqlAlchemyAuthRepository)
        media = MediaService(uow_factory, resolved, storage, logger, SqlAlchemyMediaRepository)
        content = ContentService(uow_factory, logger, SqlAlchemyContentRepository)
        notifications = NotificationService(
            uow_factory, email, logger, SqlAlchemyNotificationRepository
        )
        portfolio = PortfolioService(
            uow_factory, media, logger, SqlAlchemyPortfolioRepository, content
        )
        teams = TeamService(
            uow_factory,
            resolved.email,
            email,
            auth,
            media,
            logger,
            portfolio,
            notifications,
            content,
            SqlAlchemyTeamRepository,
        )
        users = UserService(uow_factory, media, notifications, logger, SqlAlchemyUserRepository)
        video = VideoService(uow_factory, logger, media, SqlAlchemyVideoRepository)
        admin = AdminService(
            uow_factory,
            content,
            notifications,
            teams,
            users,
            portfolio,
            video,
            email,
            logger,
            SqlAlchemyAdminRepository,
        )
        password_reset = PasswordResetService(
            uow_factory, resolved.email, email, logger, SqlAlchemyAuthRepository
        )
        application.state.container = AppContainer(
            resolved,
            engine,
            session_factory,
            limiter,
            logger,
            metrics,
            storage,
            email,
            auth,
            users,
            teams,
            media,
            portfolio,
            video,
            notifications,
            content,
            admin,
            password_reset,
        )
        await content.ensure_settings()
        await _bootstrap_admin(application.state.container)
        logger.info(
            "application.ready",
            provider=resolved.database.url.split(":", 1)[0],
            storage=resolved.storage.provider,
            scanner=scanner.provider,
            email=resolved.email.mode,
            rate_limiter=limiter.name,
        )
        try:
            yield
        finally:
            logger.info("application.shutdown")
            await limiter.close()
            if storage_redis is not None:
                await storage_redis.aclose()
            await engine.dispose()

    application = FastAPI(
        title="ЛУГ 2026 API",
        version=resolved.app.build_version,
        description="Modular monolith API for LUG 2026 competition registration and review.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    # Install before routes so every module gets identical request/error policy.
    install_http(application, resolved, http_logger, http_metrics)
    _install_openapi_contract(application)
    application.include_router(content_router)
    application.include_router(auth_router)
    application.include_router(password_router)
    application.include_router(teams_router)
    application.include_router(media_router)
    application.include_router(users_router)
    application.include_router(portfolio_router)
    application.include_router(video_router)
    application.include_router(notifications_router)
    application.include_router(admin_router)
    application.include_router(operations_router)
    return application


def _install_openapi_contract(application: FastAPI) -> None:
    """Add the cookie/CSRF schemes and a shared legacy-compatible error schema."""

    def custom_openapi() -> dict[str, Any]:
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            description=application.description,
            routes=application.routes,
        )
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes.update(
            {
                "sessionCookie": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "lug_session",
                    "description": "HttpOnly session cookie issued after login or email verification.",
                },
                "csrfHeader": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-CSRF-Token",
                    "description": "Must match the lug_csrf cookie for state-changing requests.",
                },
                "operationsBearer": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "Operations token for readiness and metrics in staging/production.",
                },
            }
        )
        components.setdefault("schemas", {})["ErrorBody"] = {
            "type": "object",
            "required": ["error", "code"],
            "properties": {
                "error": {"type": "string"},
                "code": {"type": "string"},
                "details": {},
            },
            "description": "Stable legacy-compatible application error envelope.",
        }
        error_response = {
            "description": "Application error",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorBody"}}},
        }
        public_paths = {
            "/health",
            "/healthz",
            "/livez",
            "/version",
            "/api/openapi.json",
            "/api/config",
            "/api/results",
            "/api/session",
            "/api/invites/{code}",
        }
        csrf_only_prefixes = (
            "/api/auth/login",
            "/api/auth/register-team",
            "/api/auth/join-team",
            "/api/auth/verify-email",
            "/api/auth/resend-email-code",
            "/api/auth/request-password-reset",
            "/api/auth/reset-password",
            "/api/auth/student-card/",
        )
        for path, operations in schema.get("paths", {}).items():
            for method, operation in operations.items():
                if method == "parameters" or not isinstance(operation, dict):
                    continue
                responses = operation.setdefault("responses", {})
                for status in ("400", "401", "403", "404", "409", "422", "429", "500"):
                    responses[status] = error_response
                if path in public_paths:
                    continue
                if path in {"/ready", "/readyz", "/metrics"}:
                    operation["security"] = [{"operationsBearer": []}]
                elif path.startswith("/uploads/"):
                    operation["security"] = [{"sessionCookie": []}]
                elif path.startswith(csrf_only_prefixes):
                    operation["security"] = [{"csrfHeader": []}]
                elif path.startswith("/api/"):
                    operation["security"] = (
                        [{"sessionCookie": [], "csrfHeader": []}]
                        if method.lower() in {"post", "put", "patch", "delete"}
                        else [{"sessionCookie": []}]
                    )
        application.openapi_schema = schema
        return schema

    application.openapi = custom_openapi  # type: ignore[method-assign]


async def _bootstrap_admin(container: AppContainer) -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    from sqlalchemy import select

    from .core.security import hash_password, normalize_email, strong_password
    from .db.models import UserRow

    email = normalize_email(container.settings.security.admin_email)
    password = container.settings.security.admin_password
    async with container.new_uow() as uow:
        admin = await uow.session.scalar(select(UserRow).where(UserRow.role == "admin"))
        if admin is None and strong_password(password):
            uow.session.add(
                UserRow(
                    id=str(uuid4()),
                    email=email,
                    password_hash=await hash_password(password),
                    role="admin",
                    fio="Оргкомитет",
                    email_verified=True,
                    identity_status="approved",
                    consent_at=datetime.now(timezone.utc),
                )
            )
            await uow.session.flush()


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=4174, reload=False)
