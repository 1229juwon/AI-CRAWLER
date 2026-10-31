from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import CollectionJob, CollectionKeyword, CollectionTask
from app.db.session import get_session
from app.workers.youtube_tasks import collect_youtube

router = APIRouter(prefix="/collection-jobs", tags=["collections"])


class CollectionCreateRequest(BaseModel):
    request_text: str = Field(min_length=1, max_length=5000)
    query: str = Field(min_length=1, max_length=500)
    order: str = Field(default="relevance", pattern="^(relevance|date|rating|title|viewCount)$")
    page_size: int = Field(default=50, ge=1, le=50)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_collection(
    payload: CollectionCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    job = CollectionJob(request_text=payload.request_text)
    task = CollectionTask(
        job=job,
        platform="youtube",
        parameters={"query": payload.query, "order": payload.order, "page_size": payload.page_size},
    )
    task.keywords.append(CollectionKeyword(keyword=payload.query))
    session.add(job)
    await session.commit()
    await session.refresh(task)
    collect_youtube.delay(str(task.id))
    return {"job_id": str(job.id), "task_id": str(task.id), "status": task.status.value}


@router.get("/{job_id}")
async def get_collection(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await session.scalar(
        select(CollectionJob)
        .options(selectinload(CollectionJob.tasks))
        .where(CollectionJob.id == job_id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    return {
        "job_id": str(job.id),
        "status": job.status.value,
        "tasks": [
            {"task_id": str(task.id), "platform": task.platform, "status": task.status.value, "error": task.error_message}
            for task in job.tasks
        ],
    }
