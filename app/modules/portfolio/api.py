"""HTTP adapter for achievements."""

from typing import Annotated

from fastapi import APIRouter, Path, Request

from ...api_models.common import SuccessResponse
from ...api_models.portfolio import AchievementRequest, AchievementResponse
from ...core.dependencies import Container, CurrentUser
from ...core.http import json_response

router = APIRouter(prefix="/api", tags=["Participant"])


@router.post(
    "/achievements",
    response_model=AchievementResponse,
    status_code=201,
    summary="Create a portfolio achievement",
)
async def create_achievement(
    payload: AchievementRequest, request: Request, user: CurrentUser, app_container: Container
):
    return json_response(
        {
            "achievement": await app_container.portfolio.create(
                user, payload.model_dump(by_alias=True)
            )
        },
        201,
        request,
    )


@router.delete(
    "/achievements/{id}", response_model=SuccessResponse, summary="Delete a portfolio achievement"
)
async def delete_achievement(
    achievement_id: Annotated[str, Path(alias="id")],
    request: Request,
    user: CurrentUser,
    app_container: Container,
):
    await app_container.portfolio.delete(user, achievement_id)
    return json_response({"success": True}, request=request)
