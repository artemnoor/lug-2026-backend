"""Video request and review contracts."""

from pydantic import Field

from .common import StrictModel, VideoCard


class VideoUpdateRequest(StrictModel):
    url: str = Field(default="", max_length=1000)
    video_url: str = Field(default="", alias="videoUrl", max_length=1000)
    file_url: str = Field(default="", alias="fileUrl", max_length=500)


class VideoResponse(StrictModel):
    videoCard: VideoCard
