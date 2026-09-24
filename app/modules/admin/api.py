"""Admin HTTP façade over domain use cases."""

from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Path, Query, Request

from ...api_models.admin import (
    AchievementMutationResponse,
    AdminOverviewResponse,
    AuditResponse,
    BroadcastRequest,
    BroadcastResponse,
    CollectionResponse,
    QuotaRequest,
    ReviewRequest,
    SettingsResponse,
    TeamMutationResponse,
    UserMutationResponse,
    VideoMutationResponse,
)
from ...api_models.common import SuccessResponse
from ...api_models.content import SettingsUpdateRequest
from ...core.dependencies import AdminUser, Container
from ...core.http import json_response

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/overview", response_model=AdminOverviewResponse, summary="Get the organizer overview")
async def overview(request: Request, user: AdminUser, app_container: Container):
    return json_response(await app_container.admin.overview(), request=request)


@router.get(
    "/collections/{resource}",
    response_model=CollectionResponse,
    summary="List an organizer collection",
)
async def collection(
    resource: str,
    request: Request,
    user: AdminUser,
    app_container: Container,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    query: str = Query("", max_length=120),
    status: str = Query("all", max_length=40),
):
    return json_response(
        await app_container.admin.collection(resource, limit, offset, query, status),
        request=request,
    )


@router.get("/audit", response_model=AuditResponse, summary="List the audit log")
async def audit(request: Request, user: AdminUser, app_container: Container):
    return json_response({"auditLog": await app_container.admin.audit()}, request=request)


@router.patch(
    "/teams/{teamId}/quota", response_model=TeamMutationResponse, summary="Confirm team quota"
)
async def quota(
    team_id: Annotated[str, Path(alias="teamId")],
    payload: QuotaRequest,
    request: Request,
    user: AdminUser,
    app_container: Container,
):
    return json_response(
        {
            "team": await app_container.admin.confirm_quota(
                unquote(team_id), payload.confirmed, user["id"]
            )
        },
        request=request,
    )


@router.patch(
    "/teams/{teamId}/review", response_model=TeamMutationResponse, summary="Review team data"
)
async def review_team(
    team_id: Annotated[str, Path(alias="teamId")],
    payload: ReviewRequest,
    request: Request,
    user: AdminUser,
    app_container: Container,
):
    return json_response(
        {
            "team": await app_container.admin.review_team(
                unquote(team_id), payload.model_dump(by_alias=True), user["id"]
            )
        },
        request=request,
    )


@router.delete(
    "/teams/{teamId}/members/{userId}",
    response_model=SuccessResponse,
    summary="Remove a team member",
)
async def remove_member(
    team_id: Annotated[str, Path(alias="teamId")],
    user_id: Annotated[str, Path(alias="userId")],
    request: Request,
    user: AdminUser,
    app_container: Container,
):
    await app_container.admin.remove_member(unquote(team_id), unquote(user_id), user["id"])
    return json_response({"success": True}, request=request)


@router.patch(
    "/users/{userId}/identity",
    response_model=UserMutationResponse,
    summary="Review participant identity",
)
async def review_identity(
    user_id: Annotated[str, Path(alias="userId")],
    payload: ReviewRequest,
    request: Request,
    user: AdminUser,
    app_container: Container,
):
    return json_response(
        {
            "user": await app_container.admin.review_identity(
                unquote(user_id), payload.model_dump(by_alias=True), user["id"]
            )
        },
        request=request,
    )


@router.patch(
    "/achievements/{id}/review",
    response_model=AchievementMutationResponse,
    summary="Review an achievement",
)
async def review_achievement(
    achievement_id: Annotated[str, Path(alias="id")],
    payload: ReviewRequest,
    request: Request,
    user: AdminUser,
    app_container: Container,
):
    return json_response(
        {
            "achievement": await app_container.admin.review_achievement(
                unquote(achievement_id), payload.model_dump(by_alias=True), user["id"]
            )
        },
        request=request,
    )


@router.patch(
    "/videos/{teamId}/review", response_model=VideoMutationResponse, summary="Review team video"
)
async def review_video(
    team_id: Annotated[str, Path(alias="teamId")],
    payload: ReviewRequest,
    request: Request,
    user: AdminUser,
    app_container: Container,
):
    return json_response(
        {
            "videoCard": await app_container.admin.review_video(
                unquote(team_id), payload.model_dump(by_alias=True), user["id"]
            )
        },
        request=request,
    )


@router.patch("/settings", response_model=SettingsResponse, summary="Update competition settings")
async def update_settings(
    payload: SettingsUpdateRequest, request: Request, user: AdminUser, app_container: Container
):
    return json_response(
        {
            "settings": await app_container.admin.update_settings(
                payload.model_dump(exclude_none=True), user["id"]
            )
        },
        request=request,
    )


@router.post(
    "/notifications/broadcast",
    response_model=BroadcastResponse,
    status_code=201,
    summary="Broadcast an organizer notification",
)
async def broadcast(
    payload: BroadcastRequest, request: Request, user: AdminUser, app_container: Container
):
    return json_response(
        await app_container.admin.broadcast(payload.model_dump(by_alias=True), user["id"]),
        201,
        request,
    )
