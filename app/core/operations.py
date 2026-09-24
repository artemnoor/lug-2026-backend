"""Liveness, readiness, metrics, version, and private object delivery."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

from ..api_models.common import HealthResponse, ReadinessResponse, VersionResponse
from .database import ping_database
from .dependencies import Container
from .errors import AuthenticationError, AuthorizationError, NotFoundError
from .http import json_response

router = APIRouter(tags=["Operations"])


@router.get("/health", summary="Process liveness", response_model=HealthResponse)
async def health(request: Request, app_container: Container):
    settings = app_container.settings
    return json_response(
        {"status": "ok", "service": settings.app.name, "version": settings.app.build_version},
        request=request,
    )


@router.get("/healthz", summary="Legacy process liveness alias", response_model=HealthResponse)
async def healthz(request: Request, app_container: Container):
    return await health(request, app_container)


@router.get("/livez", summary="Lightweight liveness", response_model=HealthResponse)
async def livez(request: Request, app_container: Container):
    return await health(request, app_container)


async def _operations_access(request: Request, app_container: Container) -> None:
    token = app_container.settings.security.operations_token
    if token and request.headers.get("Authorization") == f"Bearer {token}":
        return
    if (
        not token
        and request.client
        and request.client.host in {"127.0.0.1", "::1", "localhost", "testclient", "testserver"}
    ):
        return
    raise NotFoundError("Маршрут не найден.", "OPERATIONS_NOT_FOUND")


@router.get("/ready", summary="Dependency readiness", response_model=ReadinessResponse)
async def ready(request: Request, app_container: Container):
    await _operations_access(request, app_container)
    db_ready = await ping_database(app_container.engine)
    rate_ready = await app_container.rate_limiter.ready()
    storage_ready = await app_container.storage.ready()
    email_ready = await app_container.email.ready()
    if not (db_ready and rate_ready and storage_ready and email_ready):
        return json_response(
            {
                "status": "not_ready",
                "service": app_container.settings.app.name,
                "dependencies": {
                    "database": db_ready,
                    "rateLimiter": rate_ready,
                    "storage": storage_ready,
                    "email": email_ready,
                },
            },
            503,
            request,
        )
    return json_response(
        {"status": "ready", "service": app_container.settings.app.name}, request=request
    )


@router.get(
    "/readyz", summary="Legacy dependency readiness alias", response_model=ReadinessResponse
)
async def readyz(request: Request, app_container: Container):
    return await ready(request, app_container)


@router.get("/metrics", response_class=PlainTextResponse, summary="Prometheus metrics")
async def metrics(request: Request, app_container: Container):
    await _operations_access(request, app_container)
    response = PlainTextResponse(
        app_container.metrics.prometheus(), media_type="text/plain; version=0.0.4"
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-Id"] = request.state.request_id
    return response


@router.get("/version", summary="Build metadata", response_model=VersionResponse)
async def version(request: Request, app_container: Container):
    return json_response(
        {
            "service": app_container.settings.app.name,
            "version": app_container.settings.app.build_version,
            "sha": app_container.settings.app.build_sha,
        },
        request=request,
    )


@router.get(
    "/api/openapi.json",
    summary="OpenAPI document compatibility alias",
    response_model=dict[str, object],
)
async def openapi_json(request: Request):
    response = json_response(request.app.openapi(), request=request)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get(
    "/uploads/{filename:path}", include_in_schema=True, summary="Read an authorized private upload"
)
async def private_upload(filename: str, request: Request, app_container: Container):
    user = await _get_user(request, app_container)
    upload = await app_container.media.get_upload_by_url(f"/uploads/{filename}")
    if upload is None:
        raise NotFoundError("Файл не найден.", "UPLOAD_NOT_FOUND")
    if not await app_container.media.can_read_upload(user, upload):
        raise AuthorizationError("Недостаточно прав для доступа к файлу.", "UPLOAD_NOT_OWNED")
    if upload["scan_status"] != "clean":
        raise AuthorizationError("Файл ещё не прошёл проверку безопасности.", "UPLOAD_SCAN_PENDING")
    if request.method == "HEAD":
        return Response(
            status_code=200,
            headers={
                "Content-Length": str(upload["size_bytes"]),
                "Cache-Control": "private, no-store",
            },
        )
    return await app_container.storage.response(upload, request)


@router.head("/uploads/{filename:path}", include_in_schema=False)
async def private_upload_head(filename: str, request: Request, app_container: Container):
    return await private_upload(filename, request, app_container)


async def _get_user(request: Request, app_container: Container) -> dict:
    from .security import SESSION_COOKIE, hash_token

    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise AuthenticationError("Требуется вход для доступа к файлу.")
    user = await app_container.auth.get_by_session(hash_token(token))
    if not user:
        raise AuthenticationError("Требуется вход для доступа к файлу.")
    return user
