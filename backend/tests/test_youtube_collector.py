import httpx
import pytest

from app.collectors.base import SearchRequest
from app.collectors.youtube.client import YouTubeClient, YouTubeQuotaExceeded
from app.collectors.youtube.collector import YouTubeCollector
from app.services.quota import QuotaLedger, QuotaUnavailable


def response(request: httpx.Request, payload: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=request)


@pytest.mark.asyncio
async def test_search_paginates_and_deduplicates_video_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        if token == "next":
            payload = {
                "items": [
                    {"id": {"videoId": "one"}, "snippet": {"title": "duplicate"}},
                    {"id": {"videoId": "two"}, "snippet": {"title": "second"}},
                ]
            }
        else:
            payload = {
                "nextPageToken": "next",
                "items": [
                    {"id": {"videoId": "one"}, "snippet": {"title": "first"}},
                    {"id": {"channelId": "not-a-video"}, "snippet": {}},
                ],
            }
        return response(request, payload)

    client = YouTubeClient("test-key", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    videos = await YouTubeCollector(client).search(SearchRequest(query="safety"))

    assert [video.platform_video_id for video in videos] == ["one", "two"]
    assert videos[0].title == "first"
    await client.aclose()


@pytest.mark.asyncio
async def test_quota_error_is_not_retried_or_hidden() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response(
            request,
            {"error": {"message": "Daily quota exceeded", "errors": [{"reason": "quotaExceeded"}]}},
            403,
        )

    client = YouTubeClient("test-key", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with pytest.raises(YouTubeQuotaExceeded):
        await client.search_page(SearchRequest(query="safety"))
    await client.aclose()


@pytest.mark.asyncio
async def test_comments_disabled_returns_empty_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response(
            request,
            {"error": {"message": "Comments disabled", "errors": [{"reason": "commentsDisabled"}]}},
            403,
        )

    client = YouTubeClient("test-key", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await YouTubeCollector(client).get_comments("video-id") == []
    await client.aclose()


def test_quota_ledger_blocks_when_remaining_quota_is_insufficient() -> None:
    ledger = QuotaLedger(daily_limit=100)
    ledger.reserve(90)
    with pytest.raises(QuotaUnavailable):
        ledger.reserve(11)
    assert ledger.remaining == 10
