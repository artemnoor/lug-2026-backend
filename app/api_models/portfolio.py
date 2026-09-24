"""Achievement request contract."""

from pydantic import Field

from .common import AchievementView, StrictModel


class AchievementRequest(StrictModel):
    title: str = Field(max_length=200)
    direction: str = Field(max_length=32)
    category: str = Field(max_length=120)
    file_url: str = Field(default="", alias="fileUrl", max_length=500)
    details: str = Field(default="", max_length=2000)
    file_name: str = Field(default="Документ", alias="fileName", max_length=255)


class AchievementResponse(StrictModel):
    achievement: AchievementView
