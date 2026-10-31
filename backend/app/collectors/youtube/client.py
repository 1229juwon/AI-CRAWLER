from collections.abc import AsyncIterator
from typing import Any

import httpx


class YouTubeApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, reason: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


class YouTubeQuotaExceeded(YouTubeApiError):
    """Raised when the API reports exhausted or insufficient quota."""


class YouTubeClient:
    base_url = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str, http_client: httpx.AsyncClient | None = None) -> None:
        if not api_key.strip():
            raise ValueError("YouTube API key must not be empty")
        self.api_key = api_key
        self.http_client = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self.http_client.aclose()

    async def _get(self, resource: str, params: dict[str, Any]) -> dict[str, Any]:
        response = await self.http_client.get(
            f"{self.base_url}/{resource}",
            params={**params, "key": self.api_key},
        )
        if response.status_code >= 400:
            payload = response.json() if response.content else {}
            error = payload.get("error", {})
            reason = next((item.get("reason") for item in error.get("errors", [])), None)
            message = error.get("message", response.text)
            if response.status_code == 403 and reason in {"quotaExceeded", "dailyLimitExceeded"}:
                raise YouTubeQuotaExceeded(message, status_code=response.status_code, reason=reason)
            raise YouTubeApiError(message, status_code=response.status_code, reason=reason)
        return response.json()

    async def search_page(
        self, request: Any, *, page_token: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet",
            "q": request.query,
            "type": "video",
            "maxResults": request.page_size,
            "order": request.order,
        }
        if page_token:
            params["pageToken"] = page_token
        if request.published_after:
            params["publishedAfter"] = request.published_after.isoformat().replace("+00:00", "Z")
        if request.published_before:
            params["publishedBefore"] = request.published_before.isoformat().replace("+00:00", "Z")
        return await self._get("search", params)

    async def paginate_search(self, request: Any) -> AsyncIterator[dict[str, Any]]:
        page_token = None
        while True:
            page = await self.search_page(request, page_token=page_token)
            yield page
            page_token = page.get("nextPageToken")
            if not page_token:
                return

    async def get_videos(self, video_ids: list[str]) -> dict[str, Any]:
        if not video_ids:
            return {"items": []}
        return await self._get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(video_ids)})

    async def get_channels(self, channel_ids: list[str]) -> dict[str, Any]:
        if not channel_ids:
            return {"items": []}
        return await self._get("channels", {"part": "snippet,statistics", "id": ",".join(channel_ids)})

    async def get_comments(self, video_id: str, *, page_token: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,
            "textFormat": "plainText",
        }
        if page_token:
            params["pageToken"] = page_token
        return await self._get("commentThreads", params)

    async def get_caption_tracks(self, video_id: str) -> dict[str, Any]:
        return await self._get("captions", {"part": "snippet", "videoId": video_id})
