"""HTTP adapter for password reset."""

from fastapi import APIRouter, Request

from ...api_models.auth import PasswordResetConfirm, PasswordResetRequest
from ...api_models.common import SuccessResponse
from ...core.dependencies import Container
from ...core.http import enforce_rate_limit, json_response

router = APIRouter(prefix="/api", tags=["Auth"])


@router.post(
    "/auth/request-password-reset",
    response_model=SuccessResponse,
    status_code=202,
    summary="Request password reset",
)
async def request_reset(payload: PasswordResetRequest, request: Request, app_container: Container):
    await enforce_rate_limit(app_container, request, "password-reset-request", 5)
    await app_container.password_reset.request(payload.email)
    return json_response(
        {"success": True, "message": "Если адрес зарегистрирован, код отправлен на почту."},
        202,
        request,
    )


@router.post(
    "/auth/reset-password", response_model=SuccessResponse, summary="Complete password reset"
)
async def reset_password(payload: PasswordResetConfirm, request: Request, app_container: Container):
    await enforce_rate_limit(app_container, request, "password-reset-confirm", 10)
    await app_container.password_reset.reset(payload.email, payload.code, payload.password)
    return json_response({"success": True}, request=request)
