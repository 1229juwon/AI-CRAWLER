from .schemas import SearchPlan
from .tools import ToolRegistry, youtube_tool_registry


class PlanValidationError(ValueError):
    """Raised when an agent plan cannot be executed safely."""


class SearchPlanValidator:
    def __init__(self, registry: ToolRegistry = youtube_tool_registry) -> None:
        self.registry = registry

    def validate(self, plan: SearchPlan) -> SearchPlan:
        if plan.platform.value != "youtube":
            raise PlanValidationError(f"unsupported platform: {plan.platform.value}")
        if any(not query.strip() for query in plan.queries):
            raise PlanValidationError("search queries must not be blank")
        try:
            self.registry.validate(plan.tools)
        except ValueError as error:
            raise PlanValidationError(str(error)) from error
        return plan
