from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.agent.schemas import SearchPlan
from app.main import app


def test_natural_language_request_is_planned_and_enqueued() -> None:
    plan = SearchPlan(
        request_text="recent safety videos",
        queries=["product safety"],
        collect_comments=False,
        collect_captions=False,
    )
    planner = SimpleNamespace(create_plan=AsyncMock(return_value=plan), aclose=AsyncMock())
    with (
        patch("app.api.agent.OpenAICompatiblePlanner", return_value=planner),
        patch("app.api.agent.collect_youtube.apply_async") as enqueue,
    ):
        enqueue.return_value = SimpleNamespace(id=str(uuid4()))
        response = TestClient(app).post(
            "/agent/requests/execute",
            json={"request_text": "recent safety videos"},
        )

    assert response.status_code == 202
    assert response.json()["agent_execution_id"]
    planner.create_plan.assert_awaited_once_with("recent safety videos")
    enqueue.assert_called_once()
