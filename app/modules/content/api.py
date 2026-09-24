"""HTTP adapter for public settings and results."""

from fastapi import APIRouter, Request

from ...api_models.content import ConfigResponse, ResultsResponse
from ...core.dependencies import Container
from ...core.http import public_json_response

router = APIRouter(prefix="/api", tags=["Public"])


@router.get("/config", response_model=ConfigResponse, summary="Get public competition settings")
async def config(request: Request, app_container: Container):
    return public_json_response({"settings": await app_container.content.get_settings()}, request)


@router.get("/results", response_model=ResultsResponse, summary="Get published competition results")
async def results(request: Request, app_container: Container):
    return public_json_response(await app_container.content.get_results(), request)
