"""HTTP adapter for team video."""

from fastapi import APIRouter, Request

from ...api_models.video import VideoResponse, VideoUpdateRequest
from ...core.dependencies import Container, CurrentUser
from ...core.http import json_response

router = APIRouter(prefix="/api", tags=["Participant"])


@router.patch("/team/video", response_model=VideoResponse, summary="Submit team video")
async def update_video(
    payload: VideoUpdateRequest, request: Request, user: CurrentUser, app_container: Container
):
    return json_response(
        {"videoCard": await app_container.video.update(user, payload.model_dump(by_alias=True))},
        request=request,
    )
