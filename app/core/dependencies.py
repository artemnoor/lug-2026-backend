"""FastAPI composition-boundary dependencies."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request

from .errors import AuthenticationError, AuthorizationError
from .security import SESSION_COOKIE, hash_token


def container(request: Request) -> Any:
    return request.app.state.container


Container = Annotated[Any, Depends(container)]


async def current_user(request: Request, app_container: Container) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise AuthenticationError()
    user = await app_container.auth.get_by_session(hash_token(token))
    if not user:
        raise AuthenticationError()
    request.state.user = user
    return dict(user)


CurrentUser = Annotated[dict[str, Any], Depends(current_user)]


def require_admin(user: CurrentUser) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise AuthorizationError("Доступ разрешён только организаторам.", "ADMIN_REQUIRED")
    return user


AdminUser = Annotated[dict[str, Any], Depends(require_admin)]
