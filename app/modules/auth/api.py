"""HTTP adapter for auth/session operations."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ...api_models.auth import (
    LoginRequest,
    LoginResponse,
    RemoveSessionsResponse,
    SessionListResponse,
    SessionResponse,
)
from ...api_models.common import SuccessResponse
from ...core.dependencies import Container, CurrentUser
from ...core.http import json_response
from ...core.security import SESSION_COOKIE, hash_token

router = APIRouter(prefix="/api", tags=["Auth"])


def _session_cookie(response: Response, token: str, container) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=container.settings.security.session_ttl_seconds,
        httponly=True,
        secure=container.settings.security.secure_cookies,
        samesite="lax",
        path="/",
    )


@router.get("/session", response_model=SessionResponse, summary="Get the current session")
async def session(request: Request, app_container: Container):
    token = request.cookies.get(SESSION_COOKIE, "")
    user = await app_container.auth.get_by_session(hash_token(token)) if token else None
    return json_response({"user": user}, request=request)


@router.get(
    "/sessions", response_model=SessionListResponse, summary="List the current user's sessions"
)
async def sessions(request: Request, user: CurrentUser, app_container: Container):
    token = request.cookies.get(SESSION_COOKIE, "")
    return json_response(
        {"sessions": await app_container.auth.list_sessions(user["id"], token)}, request=request
    )


@router.delete(
    "/sessions/others", response_model=RemoveSessionsResponse, summary="Revoke other sessions"
)
async def remove_other_sessions(request: Request, user: CurrentUser, app_container: Container):
    token = request.cookies.get(SESSION_COOKIE, "")
    return json_response(
        {"removed": await app_container.auth.revoke_other_sessions(user["id"], token)},
        request=request,
    )


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    status_code=200,
    summary="Log in with email and password",
)
async def login(payload: LoginRequest, request: Request, app_container: Container):
    result = await app_container.rate_limiter.check(
        f"auth:{request.client.host if request.client else 'unknown'}", 15
    )
    if not result.allowed:
        from ...core.errors import RateLimitError

        raise RateLimitError()
    user, token = await app_container.auth.authenticate(
        payload.email,
        payload.password,
        request.headers.get("user-agent", ""),
        request.client.host if request.client else "",
    )
    response = json_response({"user": user}, request=request)
    _session_cookie(response, token, app_container)
    return response


@router.post("/auth/logout", response_model=SuccessResponse, summary="Log out the current session")
async def logout(request: Request, app_container: Container):
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        await app_container.auth.logout(token)
    response = json_response({"success": True}, request=request)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
