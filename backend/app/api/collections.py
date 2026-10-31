from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import CollectionJob, CollectionKeyword, CollectionTask, JobStatus, TaskStatus
from app.db.session import get_session
from app.workers.celery_app import celery_app
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
    async_result = collect_youtube.apply_async(args=[str(task.id)], priority=job.priority)
    task.celery_task_id = async_result.id
    await session.commit()
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


@router.post("/{job_id}/pause")
async def pause_collection(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    job = await session.scalar(
        select(CollectionJob).options(selectinload(CollectionJob.tasks)).where(CollectionJob.id == job_id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    active_tasks = [task for task in job.tasks if task.status in {TaskStatus.pending, TaskStatus.running}]
    if not active_tasks:
        raise HTTPException(status_code=409, detail="collection job has no active tasks")
    for task in active_tasks:
        if task.celery_task_id:
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        task.status = TaskStatus.cancelled
    job.status = JobStatus.paused
    await session.commit()
    return {"job_id": str(job.id), "status": job.status.value}


@router.post("/{job_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_collection(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    job = await session.scalar(
        select(CollectionJob).options(selectinload(CollectionJob.tasks)).where(CollectionJob.id == job_id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    task = next(
        (item for item in job.tasks if item.status in {TaskStatus.cancelled, TaskStatus.waiting_quota, TaskStatus.failed}),
        None,
    )
    if task is None:
        raise HTTPException(status_code=409, detail="collection job has no resumable task")
    task.status = TaskStatus.pending
    task.error_message = None
    job.status = JobStatus.pending
    async_result = collect_youtube.apply_async(args=[str(task.id)], priority=job.priority)
    task.celery_task_id = async_result.id
    await session.commit()
    return {"job_id": str(job.id), "task_id": str(task.id), "status": task.status.value}


@router.patch("/{job_id}/priority")
async def update_priority(
    job_id: UUID,
    priority: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int | str]:
    job = await session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="collection job not found")
    if not -100 <= priority <= 100:
        raise HTTPException(status_code=422, detail="priority must be between -100 and 100")
    job.priority = priority
    await session.commit()
    return {"job_id": str(job.id), "priority": job.priority}
