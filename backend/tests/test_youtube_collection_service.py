from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.collectors.base import DiscoveredVideo, SearchRequest, VideoMetadata
from app.collectors.youtube.client import YouTubeQuotaExceeded
from app.core.config import get_settings
from app.db.models import CollectionJob, CollectionTask, JobStatus, TaskStatus, Video
from app.services.quota import QuotaLedger
from app.services.youtube_collection import YouTubeCollectionService


class FakeCollector:
    def __init__(self) -> None:
        self.video_id = f"video-{uuid4()}"

    async def search(self, request: SearchRequest) -> list[DiscoveredVideo]:
        return [
            DiscoveredVideo(self.video_id, "First", "channel-1", "Channel", datetime.now(timezone.utc), "thumb"),
            DiscoveredVideo(self.video_id, "Duplicate", "channel-1", "Channel", datetime.now(timezone.utc), "thumb"),
        ]

    async def get_metadata(self, video_id: str) -> VideoMetadata:
        return VideoMetadata(video_id, "First", "Description", "channel-1", "Channel", None, 10, 2, 1, {})

    async def get_comments(self, video_id: str) -> list[dict]:
        return [{"id": "comment-1", "snippet": {"topLevelComment": {"snippet": {
            "authorDisplayName": "Author", "textDisplay": "Hello"
        }}}}]

    async def get_caption_tracks(self, video_id: str) -> list[dict]:
        return [{"id": "caption-1", "snippet": {"language": "en", "trackKind": "standard"}}]


class QuotaExceededCollector(FakeCollector):
    async def search(self, request: SearchRequest) -> list[DiscoveredVideo]:
        raise YouTubeQuotaExceeded("quota exhausted", status_code=403, reason="quotaExceeded")


async def postgres_session():
    database_url = os.getenv("DATABASE_URL", get_settings().database_url)
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as error:
        await engine.dispose()
        pytest.skip(f"PostgreSQL integration database unavailable: {error}")
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_service_persists_deduplicated_results_and_completes_task() -> None:
    engine, session_factory = await postgres_session()
    async with session_factory() as session:
        collector = FakeCollector()
        job = CollectionJob(request_text="find safety videos")
        task = CollectionTask(job=job, platform="youtube")
        session.add(task)
        await session.commit()

        result = await YouTubeCollectionService(
            session, collector, QuotaLedger(1000)
        ).run(task.id, SearchRequest(query="safety"))

        assert result.discovered_count == 1
        assert result.metadata_count == 1
        assert result.comments_count == 1
        assert result.captions_count == 1
        assert task.status == TaskStatus.completed
        assert job.status == JobStatus.completed
        await session.execute(delete(Video).where(Video.platform_video_id == collector.video_id))
        await session.execute(delete(CollectionJob).where(CollectionJob.id == job.id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_service_pauses_without_retry_when_quota_is_insufficient() -> None:
    engine, session_factory = await postgres_session()
    async with session_factory() as session:
        collector = FakeCollector()
        job = CollectionJob(request_text="find safety videos")
        task = CollectionTask(job=job, platform="youtube")
        session.add(task)
        await session.commit()

        result = await YouTubeCollectionService(
            session, collector, QuotaLedger(100)
        ).run(task.id, SearchRequest(query="safety"))

        assert result.status == TaskStatus.waiting_quota
        assert task.status == TaskStatus.waiting_quota
        assert job.status == JobStatus.paused
        await session.execute(delete(Video).where(Video.platform_video_id == collector.video_id))
        await session.execute(delete(CollectionJob).where(CollectionJob.id == job.id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_service_pauses_when_youtube_api_reports_quota_exceeded() -> None:
    engine, session_factory = await postgres_session()
    async with session_factory() as session:
        collector = QuotaExceededCollector()
        job = CollectionJob(request_text="find safety videos")
        task = CollectionTask(job=job, platform="youtube")
        session.add(task)
        await session.commit()

        result = await YouTubeCollectionService(
            session, collector, QuotaLedger(1000)
        ).run(task.id, SearchRequest(query="safety"))

        assert result.status == TaskStatus.waiting_quota
        assert task.status == TaskStatus.waiting_quota
        assert job.status == JobStatus.paused
        await session.execute(delete(Video).where(Video.platform_video_id == collector.video_id))
        await session.execute(delete(CollectionJob).where(CollectionJob.id == job.id))
        await session.commit()
    await engine.dispose()
