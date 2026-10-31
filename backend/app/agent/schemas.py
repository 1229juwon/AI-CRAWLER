from enum import Enum

from pydantic import BaseModel, Field


class Platform(str, Enum):
    youtube = "youtube"


class SearchOrder(str, Enum):
    relevance = "relevance"
    date = "date"
    rating = "rating"
    title = "title"
    view_count = "viewCount"


class SearchPlan(BaseModel):
    request_text: str = Field(min_length=1, max_length=5000)
    platform: Platform = Platform.youtube
    queries: list[str] = Field(min_length=1, max_length=10)
    order: SearchOrder = SearchOrder.relevance
    page_size: int = Field(default=50, ge=1, le=50)
    collect_comments: bool = True
    collect_captions: bool = True

    @property
    def tools(self) -> list[str]:
        tools = ["youtube.search", "youtube.get_metadata"]
        if self.collect_comments:
            tools.append("youtube.get_comments")
        if self.collect_captions:
            tools.append("youtube.get_caption_tracks")
        return tools


class PlanValidationRequest(BaseModel):
    plan: SearchPlan
