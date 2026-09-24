"""HTTP adapter for participant notifications."""

from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Path, Request

from ...api_models.common import NotificationView, StrictModel, SuccessResponse
from ...core.dependencies import Container, CurrentUser
from ...core.errors import NotFoundError
from ...core.http import json_response

router = APIRouter(prefix="/api", tags=["Participant"])


class NotificationListResponse(StrictModel):
    notifications: list[NotificationView]


@router.get(
    "/notifications", response_model=NotificationListResponse, summary="List visible notifications"
)
async def notifications(request: Request, user: CurrentUser, app_container: Container):
    return json_response(
        {"notifications": await app_container.notifications.list_for_user(user)}, request=request
    )


@router.patch(
    "/notifications/{id}/read",
    response_model=SuccessResponse,
    summary="Mark a notification as read",
)
async def read_notification(
    notification_id: Annotated[str, Path(alias="id")],
    request: Request,
    user: CurrentUser,
    app_container: Container,
):
    if not await app_container.notifications.mark_read(unquote(notification_id), user):
        raise NotFoundError("Уведомление не найдено.", "NOTIFICATION_NOT_FOUND")
    return json_response({"success": True}, request=request)
