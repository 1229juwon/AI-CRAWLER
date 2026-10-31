from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SearchRequest:
    query: str
    published_after: datetime | None = None
    published_before: datetime | None = None
    order: str = "relevance"
    page_size: int = 50
    max_pages: int = 5


@dataclass(frozen=True)
class DiscoveredVideo:
    platform_video_id: str
    title: str
    channel_id: str | None
    channel_name: str | None
    published_at: datetime | None
    thumbnail_url: str | None


@dataclass(frozen=True)
class VideoMetadata:
    platform_video_id: str
    title: str
    description: str
    channel_id: str | None
    channel_name: str | None
    published_at: datetime | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    raw: dict


class BaseCollector(Protocol):
    async def search(self, request: SearchRequest) -> list[DiscoveredVideo]:
        ...

    async def get_metadata(self, video_id: str) -> VideoMetadata:
        ...

    async def get_comments(self, video_id: str) -> list[dict]:
        ...

    async def get_caption_tracks(self, video_id: str) -> list[dict]:
        ...
