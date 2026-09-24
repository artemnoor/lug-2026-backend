"""HTTP adapter for profile updates."""

from fastapi import APIRouter, Request

from ...api_models.users import UpdateProfileRequest, UserResponse
from ...core.dependencies import Container, CurrentUser
from ...core.http import json_response

router = APIRouter(prefix="/api", tags=["Participant"])


@router.patch("/me", response_model=UserResponse, summary="Update the authenticated profile")
async def update_profile(
    payload: UpdateProfileRequest, request: Request, user: CurrentUser, app_container: Container
):
    return json_response(
        {
            "user": await app_container.users.update_profile(
                user, payload.model_dump(by_alias=True, exclude_none=True)
            )
        },
        request=request,
    )
