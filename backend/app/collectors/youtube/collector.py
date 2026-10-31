from datetime import datetime

from app.collectors.base import DiscoveredVideo, SearchRequest, VideoMetadata

from .client import YouTubeApiError, YouTubeClient


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class YouTubeCollector:
    def __init__(self, client: YouTubeClient) -> None:
        self.client = client

    async def search(self, request: SearchRequest) -> list[DiscoveredVideo]:
        videos: dict[str, DiscoveredVideo] = {}
        async for page in self.client.paginate_search(request):
            for item in page.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if not video_id:
                    continue
                videos.setdefault(
                    video_id,
                    DiscoveredVideo(
                        platform_video_id=video_id,
                        title=snippet.get("title", ""),
                        channel_id=snippet.get("channelId"),
                        channel_name=snippet.get("channelTitle"),
                        published_at=_parse_datetime(snippet.get("publishedAt")),
                        thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                    ),
                )
        return list(videos.values())

    async def get_metadata(self, video_id: str) -> VideoMetadata:
        payload = await self.client.get_videos([video_id])
        item = next((item for item in payload.get("items", []) if item.get("id") == video_id), None)
        if item is None:
            raise LookupError(f"YouTube video not found: {video_id}")
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        return VideoMetadata(
            platform_video_id=video_id,
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            channel_id=snippet.get("channelId"),
            channel_name=snippet.get("channelTitle"),
            published_at=_parse_datetime(snippet.get("publishedAt")),
            view_count=int(statistics["viewCount"]) if "viewCount" in statistics else None,
            like_count=int(statistics["likeCount"]) if "likeCount" in statistics else None,
            comment_count=int(statistics["commentCount"]) if "commentCount" in statistics else None,
            raw=item,
        )

    async def get_comments(self, video_id: str) -> list[dict]:
        comments: list[dict] = []
        page_token = None
        while True:
            try:
                page = await self.client.get_comments(video_id, page_token=page_token)
            except YouTubeApiError as error:
                if error.reason in {"commentsDisabled", "forbidden"}:
                    return []
                raise
            comments.extend(page.get("items", []))
            page_token = page.get("nextPageToken")
            if not page_token:
                return comments

    async def get_caption_tracks(self, video_id: str) -> list[dict]:
        try:
            return (await self.client.get_caption_tracks(video_id)).get("items", [])
        except YouTubeApiError as error:
            if error.reason in {"forbidden", "videoNotFound"}:
                return []
            raise
