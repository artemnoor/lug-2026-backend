"""HTTP upload and registration-card endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...api_models.media import (
    MultipartIntentResponse,
    UploadCompleteRequest,
    UploadIntentRequest,
    UploadResponse,
)
from ...core.dependencies import Container, CurrentUser
from ...core.errors import AuthorizationError
from ...core.http import enforce_rate_limit, json_response

router = APIRouter(prefix="/api", tags=["Media"])


async def _stream_headers(request: Request) -> tuple[str, str, int]:
    name = request.headers.get("X-Upload-Name", "").strip()
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    declared = request.headers.get("content-length", "0")
    size = int(declared) if declared.isdigit() else 0
    return name, content_type, size


@router.post(
    "/auth/student-card/stream",
    response_model=UploadResponse,
    status_code=201,
    summary="Upload a registration student card",
)
async def registration_card_stream(request: Request, app_container: Container):
    await enforce_rate_limit(app_container, request, "registration-upload", 10)
    name, content_type, _ = await _stream_headers(request)
    result = await app_container.media.registration_stream(request.stream(), name, content_type)
    return json_response(result, 201, request)


@router.post(
    "/auth/student-card/intent",
    response_model=MultipartIntentResponse,
    status_code=201,
    summary="Create a registration-card multipart intent",
)
async def registration_card_intent(
    payload: UploadIntentRequest, request: Request, app_container: Container
):
    await enforce_rate_limit(app_container, request, "registration-upload", 10)
    metadata = await app_container.media.registration_intent(payload.model_dump(by_alias=True))
    return json_response(metadata, 201, request)


@router.post(
    "/auth/student-card/complete",
    response_model=UploadResponse,
    status_code=201,
    summary="Complete a registration-card multipart intent",
)
async def registration_card_complete(
    payload: UploadCompleteRequest, request: Request, app_container: Container
):
    await enforce_rate_limit(app_container, request, "registration-upload", 10)
    claim = app_container.media.verify_registration_claim(payload.registration_token)
    if claim is None or claim.get("key") != payload.key:
        raise AuthorizationError(
            "Временная загрузка документа недействительна или истекла.",
            "REGISTRATION_UPLOAD_CLAIM_INVALID",
        )
    result = await app_container.media.registration_complete(
        payload.model_dump(by_alias=True), claim
    )
    return json_response(result, 201, request)


@router.post(
    "/uploads/stream",
    response_model=UploadResponse,
    status_code=201,
    summary="Stream an authenticated upload",
)
async def upload_stream(request: Request, user: CurrentUser, app_container: Container):
    await enforce_rate_limit(app_container, request, "upload", 30)
    name, content_type, size = await _stream_headers(request)
    kind = request.headers.get("X-Upload-Kind", "attachment").strip()
    result = await app_container.media.stream_upload(
        request.stream(), user, name, content_type, kind, size
    )
    return json_response(result, 201, request)


@router.post(
    "/uploads/intent",
    response_model=MultipartIntentResponse,
    status_code=201,
    summary="Create an authenticated multipart upload",
)
async def upload_intent(
    payload: UploadIntentRequest, request: Request, user: CurrentUser, app_container: Container
):
    await enforce_rate_limit(app_container, request, "upload", 30)
    result = await app_container.media.create_intent(payload.model_dump(by_alias=True), user)
    return json_response(result, 201, request)


@router.post(
    "/uploads/complete",
    response_model=UploadResponse,
    status_code=201,
    summary="Complete an authenticated multipart upload",
)
async def upload_complete(
    payload: UploadCompleteRequest, request: Request, user: CurrentUser, app_container: Container
):
    await enforce_rate_limit(app_container, request, "upload", 30)
    result = await app_container.media.complete(payload.model_dump(by_alias=True), user)
    return json_response(result, 201, request)
