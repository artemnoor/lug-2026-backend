"""Upload HTTP contracts."""

from __future__ import annotations

from pydantic import Field

from .common import StrictModel


class UploadIntentRequest(StrictModel):
    name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(alias="contentType", min_length=1, max_length=160)
    size: int = Field(gt=0, le=250 * 1024 * 1024)
    kind: str = Field(default="attachment", max_length=32)


class UploadCompleteRequest(StrictModel):
    upload_id: str = Field(alias="uploadId", min_length=1, max_length=200)
    key: str = Field(min_length=1, max_length=500)
    name: str = Field(default="", max_length=255)
    content_type: str = Field(alias="contentType", default="", max_length=160)
    kind: str = Field(default="attachment", max_length=32)
    parts: list["MultipartPart"] = Field(default_factory=list, max_length=1000)
    registration_token: str = Field(alias="registrationToken", default="", max_length=1024)


class UploadResponse(StrictModel):
    upload_id: str = Field(alias="uploadId")
    url: str
    name: str | None = None
    content_type: str | None = Field(default=None, alias="contentType")
    size: int | None = None
    kind: str | None = None
    registration_token: str | None = Field(default=None, alias="registrationToken")


class MultipartIntentResponse(StrictModel):
    upload_id: str = Field(alias="uploadId")
    key: str
    parts: list[dict[str, object]] = Field(default_factory=list)
    registration_token: str | None = Field(default=None, alias="registrationToken")


class MultipartPart(StrictModel):
    part_number: int = Field(alias="partNumber", ge=1)
    etag: str = Field(min_length=1, max_length=500)
