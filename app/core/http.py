"""HTTP adapters: request parsing, security middleware, and error mapping."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import Message, Receive

from .config import Settings
from .errors import AppError, RateLimitError, error_payload
from .logging import JsonLogger, Metrics, new_traceparent
from .security import CSRF_COOKIE, csrf_valid

MUTATIONS = {"POST", "PUT", "PATCH", "DELETE"}


def json_response(
    data: Any,
    status_code: int = 200,
    request: Request | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = JSONResponse(data, status_code=status_code, headers=headers or {})
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("Pragma", "no-cache")
    response.headers.setdefault("Vary", "Cookie")
    if request is not None:
        response.headers["X-Request-Id"] = getattr(request.state, "request_id", "")
    return response


def public_json_response(data: Any, request: Request) -> Response:
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    etag = f'"{hashlib.sha256(encoded).hexdigest()[:24]}"'
    if request.headers.get("if-none-match", "").strip() == etag:
        response: Response = Response(status_code=304)
    else:
        response = JSONResponse(data)
    response.headers.update(
        {
            "ETag": etag,
            "Cache-Control": "public, max-age=60, must-revalidate",
            "Vary": "Accept-Encoding",
            "X-Request-Id": request.state.request_id,
        }
    )
    return response


async def enforce_rate_limit(container: Any, request: Request, scope: str, limit: int) -> None:
    """Apply an endpoint-level fixed-window limit at the HTTP boundary."""

    address = request.client.host if request.client else "unknown"
    result = await container.rate_limiter.check(f"{scope}:{address}", limit)
    if not result.allowed:
        raise RateLimitError()


def _install_json_body_limit(request: Request, max_bytes: int) -> None:
    """Bound JSON bodies even when FastAPI parses them before the endpoint runs."""

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json" and not content_type.endswith("+json"):
        return
    length = request.headers.get("content-length")
    if length and not length.isdecimal():
        raise AppError(400, "INVALID_CONTENT_LENGTH", "Некорректная длина запроса.")
    if length and int(length) > max_bytes:
        raise AppError(413, "BODY_TOO_LARGE", "Файл или запрос превышает допустимый лимит.")

    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise AppError(
            415, "CONTENT_ENCODING_UNSUPPORTED", "Сжатые тела запросов не поддерживаются."
        )

    original_receive: Receive = request.receive
    total = 0

    async def receive() -> Message:
        nonlocal total
        message = await original_receive()
        if message["type"] == "http.request":
            total += len(message.get("body", b""))
            if total > max_bytes:
                raise AppError(413, "BODY_TOO_LARGE", "Файл или запрос превышает допустимый лимит.")
        return message

    request._receive = receive


def install_http(app: FastAPI, settings: Settings, logger: JsonLogger, metrics: Metrics) -> None:
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=list(settings.security.allowed_hosts) or ["127.0.0.1"]
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "http.application_error",
            request_id=getattr(request.state, "request_id", ""),
            code=exc.code,
            status=exc.status_code,
        )
        return json_response(error_payload(exc), exc.status_code, request)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "http.validation_error",
            request_id=getattr(request.state, "request_id", ""),
            errors=exc.errors(),
        )
        return json_response(
            {
                "error": "Некорректный формат запроса.",
                "code": "VALIDATION_ERROR",
                "details": exc.errors(),
            },
            422,
            request,
        )

    @app.middleware("http")
    async def request_pipeline(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = _request_id(request)
        request.state.traceparent, request.state.trace_id = new_traceparent(
            request.headers.get("traceparent")
        )
        started = perf_counter()
        try:
            _install_json_body_limit(request, settings.security.max_json_body)
            if request.method in MUTATIONS and not csrf_valid(
                request.cookies.get(CSRF_COOKIE, ""), request.headers.get("X-CSRF-Token", "")
            ):
                response: Response = json_response(
                    {
                        "error": "Недействительный CSRF-токен. Обновите страницу и повторите действие.",
                        "code": "CSRF_INVALID",
                    },
                    403,
                    request,
                )
            else:
                response = await call_next(request)
        except AppError as exc:
            response = json_response(error_payload(exc), exc.status_code, request)
        except Exception as exc:  # pragma: no cover - covered through API smoke
            logger.error(
                "http.internal_error",
                request_id=request.state.request_id,
                trace_id=request.state.trace_id,
                error_type=type(exc).__name__,
                error_message=str(exc)[:500],
            )
            response = json_response(
                {"error": "Не удалось выполнить запрос.", "code": "INTERNAL_ERROR"},
                500,
                request,
            )
        duration = (perf_counter() - started) * 1000
        metrics.increment(f"http_requests.{response.status_code}")
        metrics.observe_request(duration)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["traceparent"] = request.state.traceparent
        if CSRF_COOKIE not in request.cookies:
            response.set_cookie(
                CSRF_COOKIE,
                uuid4().hex,
                max_age=604800,
                httponly=False,
                samesite="lax",
                secure=settings.security.secure_cookies,
                path="/",
            )
        _security_headers(response, settings)
        logger.info(
            "http.request",
            request_id=request.state.request_id,
            trace_id=request.state.trace_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration, 2),
        )
        return response


def _request_id(request: Request) -> str:
    value = request.headers.get("X-Request-Id", "").strip()
    return (
        value[:120]
        if value and all(char.isalnum() or char in "._:-" for char in value)
        else str(uuid4())
    )


def _security_headers(response: Response, settings: Settings) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if settings.security.secure_cookies:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
