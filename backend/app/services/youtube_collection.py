from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import SearchRequest
from app.collectors.youtube.client import YouTubeApiError, YouTubeQuotaExceeded
from app.collectors.youtube.collector import YouTubeCollector
from app.db.models import (
    CollectionJob,
    CollectionLog,
    CollectionTask,
    JobStatus,
    PlatformSource,
    TaskStatus,
    Video,
    VideoCaption,
    VideoComment,
    VideoMetadataStatus,
)
from app.services.quota import QuotaLedger, QuotaUnavailable


@dataclass(frozen=True)
class CollectionResult:
    discovered_count: int
    metadata_count: int
    comments_count: int
    captions_count: int
    status: TaskStatus


class YouTubeCollectionService:
    """Persist one YouTube collection task without downloading media."""

    def __init__(
        self,
        session: AsyncSession,
        collector: YouTubeCollector,
        quota: QuotaLedger,
    ) -> None:
        self.session = session
        self.collector = collector
        self.quota = quota

    async def run(
        self,
        task_id: UUID,
        request: SearchRequest,
        *,
        collect_comments: bool = True,
        collect_captions: bool = True,
    ) -> CollectionResult:
        task = await self.session.get(CollectionTask, task_id)
        if task is None:
            raise LookupError(f"collection task not found: {task_id}")
        job = await self.session.get(CollectionJob, task.job_id)
        if job is None:
            raise LookupError(f"collection job not found: {task.job_id}")

        task.status = TaskStatus.running
        task.error_message = None
        job.status = JobStatus.running
        await self.session.flush()

        try:
            self.quota.reserve(100)
            discovered_results = await self.collector.search(request)
            discovered_by_id = {
                item.platform_video_id: item for item in discovered_results
            }
            discovered = list(discovered_by_id.values())
            source = await self._get_source()
            videos = [await self._upsert_discovered(source.id, item) for item in discovered]
            await self.session.flush()

            metadata_count = 0
            comments_count = 0
            captions_count = 0
            for video in videos:
                try:
                    self.quota.reserve(1)
                    metadata = await self.collector.get_metadata(video.platform_video_id)
                    video.title = metadata.title
                    video.channel_name = metadata.channel_name
                    video.published_at = metadata.published_at
                    video.view_count = metadata.view_count
                    video.metadata_json = metadata.raw
                    video.metadata_status = VideoMetadataStatus.collected
                    metadata_count += 1

                    if collect_comments:
                        self.quota.reserve(1)
                        comments = await self.collector.get_comments(video.platform_video_id)
                        comments_count += await self._persist_comments(video.id, comments)

                    if collect_captions:
                        self.quota.reserve(50)
                        captions = await self.collector.get_caption_tracks(video.platform_video_id)
                        captions_count += await self._persist_captions(video.id, captions)
                except QuotaUnavailable:
                    task.status = TaskStatus.waiting_quota
                    task.error_message = "YouTube API quota is insufficient; task paused without retrying."
                    job.status = JobStatus.paused
                    await self._log(task, "quota_wait", task.error_message)
                    await self.session.commit()
                    return CollectionResult(
                        len(discovered), metadata_count, comments_count, captions_count, task.status
                    )

            task.status = TaskStatus.completed
            job.status = JobStatus.completed
            await self._log(task, "task_completed", f"Persisted {len(videos)} discovered videos.")
            await self.session.commit()
            return CollectionResult(
                len(discovered), metadata_count, comments_count, captions_count, task.status
            )
        except YouTubeQuotaExceeded as error:
            await self.session.rollback()
            task = await self.session.get(CollectionTask, task_id)
            if task is None:
                raise
            task.status = TaskStatus.waiting_quota
            task.error_message = "YouTube API quota is exhausted; task paused without retrying."
            job = await self.session.get(CollectionJob, task.job_id)
            if job is not None:
                job.status = JobStatus.paused
            await self._log(task, "quota_wait", task.error_message)
            await self.session.commit()
            return CollectionResult(0, 0, 0, 0, task.status)
        except (YouTubeApiError, LookupError, SQLAlchemyError) as error:
            await self.session.rollback()
            task = await self.session.get(CollectionTask, task_id)
            if task is None:
                raise
            task.status = TaskStatus.failed
            task.error_message = str(error)
            job = await self.session.get(CollectionJob, task.job_id)
            if job is not None:
                job.status = JobStatus.failed
            await self._log(task, "task_failed", str(error))
            await self.session.commit()
            raise

    async def _get_source(self) -> PlatformSource:
        source = await self.session.scalar(
            select(PlatformSource).where(PlatformSource.platform == "youtube")
        )
        if source is None:
            source = PlatformSource(
                platform="youtube",
                display_name="YouTube",
                base_url="https://www.youtube.com",
            )
            self.session.add(source)
            await self.session.flush()
        return source

    async def _upsert_discovered(self, source_id: UUID, item: object) -> Video:
        video = await self.session.scalar(
            select(Video).where(
                Video.source_id == source_id,
                Video.platform_video_id == item.platform_video_id,
            )
        )
        if video is None:
            video = Video(
                source_id=source_id,
                platform_video_id=item.platform_video_id,
                title=item.title,
                channel_name=item.channel_name,
                published_at=item.published_at,
                metadata_json={"thumbnail_url": item.thumbnail_url},
            )
            self.session.add(video)
        else:
            video.title = item.title
            video.channel_name = item.channel_name
            video.published_at = item.published_at
            video.metadata_json = {
                **(video.metadata_json or {}),
                "thumbnail_url": item.thumbnail_url,
            }
        return video

    async def _persist_comments(self, video_id: UUID, comments: list[dict]) -> int:
        persisted = 0
        for item in comments:
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            comment_id = item.get("id")
            if not comment_id:
                continue
            existing = await self.session.scalar(
                select(VideoComment).where(
                    VideoComment.video_id == video_id,
                    VideoComment.platform_comment_id == comment_id,
                )
            )
            if existing is None:
                self.session.add(
                    VideoComment(
                        video_id=video_id,
                        platform_comment_id=comment_id,
                        author_name=self._clean_text(snippet.get("authorDisplayName")),
                        text=self._clean_text(snippet.get("textDisplay", "")),
                        published_at=self._parse_datetime(snippet.get("publishedAt")),
                    )
                )
                persisted += 1
        return persisted

    async def _persist_captions(self, video_id: UUID, captions: list[dict]) -> int:
        persisted = 0
        for item in captions:
            snippet = item.get("snippet", {})
            language = snippet.get("language")
            track_id = item.get("id")
            if not language or not track_id:
                continue
            existing = await self.session.scalar(
                select(VideoCaption).where(
                    VideoCaption.video_id == video_id,
                    VideoCaption.language == language,
                )
            )
            if existing is None:
                self.session.add(
                    VideoCaption(
                        video_id=video_id,
                        language=language,
                        source="youtube",
                        has_access=snippet.get("trackKind") != "asr",
                        object_key=None,
                    )
                )
                persisted += 1
        return persisted

    async def _log(self, task: CollectionTask, event_type: str, message: str) -> None:
        self.session.add(
            CollectionLog(
                job_id=task.job_id,
                task_id=task.id,
                level="INFO" if event_type != "task_failed" else "ERROR",
                event_type=event_type,
                message=message,
                details={},
            )
        )

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        return value.replace("\x00", "") if value is not None else None
