import pytest
from pydantic import ValidationError

from app.agent.planner import PlanValidationError, SearchPlanValidator
from app.agent.schemas import Platform, SearchPlan
from app.agent.tools import youtube_tool_registry


def test_registry_contains_only_explicit_youtube_tools() -> None:
    assert youtube_tool_registry.names() == (
        "youtube.get_caption_tracks",
        "youtube.get_comments",
        "youtube.get_metadata",
        "youtube.search",
    )


def test_plan_validator_returns_registered_tools() -> None:
    plan = SearchPlan(
        request_text="recent safety videos",
        queries=["product safety", "child safety"],
        collect_captions=False,
    )

    validated = SearchPlanValidator().validate(plan)

    assert validated.platform is Platform.youtube
    assert validated.tools == [
        "youtube.search",
        "youtube.get_metadata",
        "youtube.get_comments",
    ]


def test_plan_rejects_blank_query() -> None:
    plan = SearchPlan(request_text="find videos", queries=["valid"])
    plan.queries.append(" ")

    with pytest.raises(PlanValidationError, match="must not be blank"):
        SearchPlanValidator().validate(plan)


def test_plan_schema_rejects_empty_queries() -> None:
    with pytest.raises(ValidationError):
        SearchPlan(request_text="find videos", queries=[])
