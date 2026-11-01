"""YouTube search and MP4 download endpoints."""

from fastapi import APIRouter, HTTPException

from app.collectors.base import SearchRequest
from app.collectors.youtube.client import YouTubeClient, YouTubeApiError
from app.collectors.youtube.collector import YouTubeCollector
from app.core.config import get_settings
from app.services.youtube_download import YouTubeDownloadService, YouTubeDownloadError

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/search")
async def search_videos(
    q: str = "tech",
    max_results: int = 5,
) -> dict:
    """Search YouTube videos and return metadata."""
    settings = get_settings()
    api_key = (
        settings.youtube_api_key_sub.get_secret_value()
        or settings.youtube_api_key.get_secret_value()
    )
    if not api_key:
        raise HTTPException(status_code=500, detail="YouTube API key is not configured")

    client = YouTubeClient(api_key)
    collector = YouTubeCollector(client)
    request = SearchRequest(query=q, page_size=max_results, max_pages=1)

    try:
        videos = await collector.search(request)
        return {
            "query": q,
            "count": len(videos),
            "videos": [
                {
                    "video_id": v.platform_video_id,
                    "title": v.title,
                    "channel_name": v.channel_name,
                    "published_at": v.published_at.isoformat() if v.published_at else None,
                    "thumbnail_url": v.thumbnail_url,
                }
                for v in videos
            ],
        }
    except YouTubeApiError as exc:
        raise HTTPException(status_code=exc.status_code or 500, detail=str(exc))
    finally:
        await client.aclose()


@router.post("/download/{video_id}")
async def download_video(video_id: str) -> dict:
    """Search YouTube and download up to 5 videos as MP4 to local folder."""
    settings = get_settings()
    api_key = (
        settings.youtube_api_key_sub.get_secret_value()
        or settings.youtube_api_key.get_secret_value()
    )
    if not api_key:
        raise HTTPException(status_code=500, detail="YouTube API key is not configured")

    client = YouTubeClient(api_key)
    collector = YouTubeCollector(client)
    request = SearchRequest(query="", page_size=5, max_pages=1)

    try:
        videos = await collector.search(request)
    except YouTubeApiError as exc:
        await client.aclose()
        raise HTTPException(status_code=exc.status_code or 500, detail=str(exc))

    if not videos:
        await client.aclose()
        raise HTTPException(status_code=404, detail="No videos found")

    download_service = YouTubeDownloadService(output_dir="downloads")
    downloaded = []

    for video in videos[:5]:
        try:
            result = download_service.download(video.platform_video_id)
            downloaded.append({
                "video_id": result["video_id"],
                "title": result["title"],
                "file_path": result["file_path"],
                "file_size_bytes": result["file_size_bytes"],
            })
        except YouTubeDownloadError as exc:
            downloaded.append({
                "video_id": video.platform_video_id,
                "title": video.title,
                "error": str(exc),
            })

    await client.aclose()

    return {
        "searched_count": len(videos),
        "downloaded_count": len(downloaded),
        "videos": downloaded,
        "output_dir": str(download_service.output_dir),
    }