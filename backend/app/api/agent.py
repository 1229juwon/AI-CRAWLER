from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.planner import PlanValidationError, SearchPlanValidator
from app.agent.schemas import PlanValidationRequest, SearchPlan
from sqlalchemy import select
from app.db.models import AgentExecution, CollectionJob, CollectionKeyword, CollectionTask
from app.db.session import get_session
from app.workers.youtube_tasks import collect_youtube

router = APIRouter(prefix="/agent", tags=["agent"])
validator = SearchPlanValidator()


@router.post("/plans/validate")
async def validate_plan(payload: PlanValidationRequest) -> dict:
    try:
        plan = validator.validate(payload.plan)
    except PlanValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"valid": True, "platform": plan.platform.value, "queries": plan.queries, "tools": plan.tools}


@router.post("/plans/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_plan(
    plan: SearchPlan,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        validator.validate(plan)
    except PlanValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    job = CollectionJob(request_text=plan.request_text)
    task = CollectionTask(
        job=job,
        platform=plan.platform.value,
        parameters={
            "query": plan.queries[0],
            "queries": plan.queries,
            "order": plan.order.value,
            "page_size": plan.page_size,
            "collect_comments": plan.collect_comments,
            "collect_captions": plan.collect_captions,
        },
    )
    for query in plan.queries:
        task.keywords.append(CollectionKeyword(keyword=query))
    execution = AgentExecution(
        job=job,
        request_text=plan.request_text,
        plan=plan.model_dump(mode="json"),
        tools_called=plan.tools,
        result={"status": "queued"},
    )
    session.add_all([job, execution])
    await session.commit()
    await session.refresh(task)
    async_result = collect_youtube.apply_async(args=[str(task.id)], priority=job.priority)
    task.celery_task_id = async_result.id
    execution.result = {"status": "queued", "celery_task_id": async_result.id}
    await session.commit()
    return {"job_id": str(job.id), "task_id": str(task.id), "agent_execution_id": str(execution.id)}


@router.get("/executions")
async def list_agent_executions(
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    executions = (
        await session.scalars(
            select(AgentExecution).order_by(AgentExecution.created_at.desc()).limit(50)
        )
    ).all()
    return [
        {
            "id": str(execution.id),
            "job_id": str(execution.job_id) if execution.job_id else None,
            "request_text": execution.request_text,
            "plan": execution.plan,
            "tools_called": execution.tools_called,
            "result": execution.result,
            "error": execution.error_message,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
        }
        for execution in executions
    ]


@router.get("/executions/{execution_id}")
async def get_agent_execution(
    execution_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    execution = await session.get(AgentExecution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="agent execution not found")
    return {
        "id": str(execution.id),
        "job_id": str(execution.job_id) if execution.job_id else None,
        "request_text": execution.request_text,
        "plan": execution.plan,
        "tools_called": execution.tools_called,
        "result": execution.result,
        "error": execution.error_message,
        "created_at": execution.created_at.isoformat() if execution.created_at else None,
        "updated_at": execution.updated_at.isoformat() if execution.updated_at else None,
    }
