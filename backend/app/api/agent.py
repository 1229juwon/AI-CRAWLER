from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.planner import PlanValidationError, SearchPlanValidator
from app.agent.schemas import PlanValidationRequest, SearchPlan
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
    collect_youtube.delay(str(task.id))
    return {"job_id": str(job.id), "task_id": str(task.id), "agent_execution_id": str(execution.id)}
