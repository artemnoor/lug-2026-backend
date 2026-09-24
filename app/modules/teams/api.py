"""HTTP adapter for teams and registration."""

from __future__ import annotations

from urllib.parse import unquote

from fastapi import APIRouter, Request

from ...api_models.common import DashboardResponse
from ...api_models.teams import (
    InviteResponse,
    InviteRotationResponse,
    PendingRegistrationResponse,
    RegisterTeamRequest,
    ResendEmailRequest,
    TeamResponse,
    TeamUpdateRequest,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from ...core.dependencies import Container, CurrentUser
from ...core.http import enforce_rate_limit, json_response

router = APIRouter(prefix="/api", tags=["Teams"])


@router.post(
    "/auth/register-team",
    response_model=PendingRegistrationResponse,
    status_code=202,
    summary="Start team registration",
)
async def register_team(payload: RegisterTeamRequest, request: Request, app_container: Container):
    await enforce_rate_limit(app_container, request, "registration", 5)
    data = payload.model_dump(by_alias=True)
    return json_response(await app_container.teams.begin_registration(data, "team"), 202, request)


@router.post(
    "/auth/join-team",
    response_model=PendingRegistrationResponse,
    status_code=202,
    summary="Start invite-based team join",
)
async def join_team(payload: RegisterTeamRequest, request: Request, app_container: Container):
    await enforce_rate_limit(app_container, request, "join", 10)
    data = payload.model_dump(by_alias=True)
    return json_response(
        await app_container.teams.begin_registration(data, "participant"), 202, request
    )


@router.post(
    "/auth/verify-email",
    response_model=VerifyEmailResponse,
    status_code=201,
    summary="Verify email and create session",
)
async def verify_email(payload: VerifyEmailRequest, request: Request, app_container: Container):
    await enforce_rate_limit(app_container, request, "email-verification", 10)
    user, token = await app_container.teams.verify_email(
        payload.verification_id,
        payload.code,
        request.headers.get("user-agent", ""),
        request.client.host if request.client else "",
    )
    response = json_response({"user": user}, 201, request)
    response.set_cookie(
        "lug_session",
        token,
        max_age=app_container.settings.security.session_ttl_seconds,
        httponly=True,
        secure=app_container.settings.security.secure_cookies,
        samesite="lax",
        path="/",
    )
    return response


@router.post(
    "/auth/resend-email-code",
    response_model=PendingRegistrationResponse,
    summary="Resend a verification code",
)
async def resend_email(payload: ResendEmailRequest, request: Request, app_container: Container):
    await enforce_rate_limit(app_container, request, "email-verification-resend", 5)
    return json_response(
        await app_container.teams.resend_email_code(payload.verification_id), request=request
    )


@router.get(
    "/invites/{code}", response_model=InviteResponse, summary="Inspect an active team invite"
)
async def invite(code: str, request: Request, app_container: Container):
    await enforce_rate_limit(app_container, request, "invite-lookup", 60)
    return json_response(await app_container.teams.get_invite(unquote(code)), request=request)


@router.get("/dashboard", response_model=DashboardResponse, summary="Get the participant dashboard")
async def dashboard(request: Request, user: CurrentUser, app_container: Container):
    projection = await app_container.teams.dashboard(user)
    from ...core.errors import NotFoundError

    if projection is None:
        raise NotFoundError("Личный кабинет не найден.", "DASHBOARD_NOT_FOUND")
    return json_response(projection, request=request)


@router.patch("/team", response_model=TeamResponse, summary="Update the captain's team")
async def update_team(
    payload: TeamUpdateRequest, request: Request, user: CurrentUser, app_container: Container
):
    return json_response(
        {
            "team": await app_container.teams.update_team(
                user, payload.model_dump(by_alias=True, exclude_none=True)
            )
        },
        request=request,
    )


@router.post("/team/invite", response_model=InviteRotationResponse, summary="Rotate a team invite")
async def rotate_invite(request: Request, user: CurrentUser, app_container: Container):
    return json_response(await app_container.teams.rotate_invite(user), request=request)
