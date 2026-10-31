import asyncio
from uuid import UUID

import httpx
from sqlalchemy import select

from app.collectors.base import SearchRequest
from app.collectors.youtube.client import YouTubeClient
from app.collectors.youtube.collector import YouTubeCollector
from app.core.config import get_settings
from app.db.models import AgentExecution, CollectionTask
from app.db.session import SessionFactory
from app.services.quota import QuotaLedger
from app.services.youtube_collection import YouTubeCollectionService

from .celery_app import celery_app


async def _run_collection(task_id: UUID) -> dict:
    settings = get_settings()
    api_key = settings.youtube_api_key.get_secret_value()
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY is required to execute a YouTube collection task")

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        client = YouTubeClient(api_key, http_client)
        async with SessionFactory() as session:
            task = await session.get(CollectionTask, task_id)
            if task is None:
                raise LookupError(f"collection task not found: {task_id}")
            parameters = task.parameters
            request = SearchRequest(
                query=parameters["query"],
                order=parameters.get("order", "relevance"),
                page_size=parameters.get("page_size", 50),
            )
            result = await YouTubeCollectionService(
                session,
                YouTubeCollector(client),
                QuotaLedger(settings.youtube_daily_quota),
            ).run(task_id, request)
            execution = await session.scalar(
                select(AgentExecution).where(AgentExecution.job_id == task.job_id)
            )
            if execution is not None:
                execution.result = {
                    "status": result.status.value,
                    "discovered_count": result.discovered_count,
                    "metadata_count": result.metadata_count,
                    "comments_count": result.comments_count,
                    "captions_count": result.captions_count,
                }
                await session.commit()
            return {
                "status": result.status.value,
                "discovered_count": result.discovered_count,
                "metadata_count": result.metadata_count,
                "comments_count": result.comments_count,
                "captions_count": result.captions_count,
            }


@celery_app.task(
    bind=True,
    name="youtube.collect",
    autoretry_for=(httpx.TimeoutException,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
)
def collect_youtube(self, task_id: str) -> dict:
    return asyncio.run(_run_collection(UUID(task_id)))
