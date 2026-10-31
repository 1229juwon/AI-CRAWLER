import json
import re
from typing import Any

import httpx

from .planner import PlanValidationError, SearchPlanValidator
from .schemas import SearchPlan


class LLMPlannerError(RuntimeError):
    """Raised when an OpenAI-compatible planner cannot return a valid plan."""


class OpenAICompatiblePlanner:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str = "",
        jwt_token: str = "",
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not endpoint.strip():
            raise ValueError("AI API endpoint must not be empty")
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.jwt_token = jwt_token
        self.http_client = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None
        self.validator = SearchPlanValidator()

    async def aclose(self) -> None:
        if self._owns_client:
            await self.http_client.aclose()

    async def create_plan(self, request_text: str) -> SearchPlan:
        if not request_text.strip():
            raise ValueError("request_text must not be blank")
        try:
            response = await self.http_client.post(
                self.endpoint,
                headers=self._headers(),
                json={
                    "model": self.model,
                    "temperature": 0,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You create safe YouTube search plans. Return JSON only with keys "
                                "request_text, platform, queries, order, page_size, collect_comments, "
                                "collect_captions. Use platform youtube and never request media downloads."
                            ),
                        },
                        {"role": "user", "content": request_text},
                    ],
                },
            )
        except httpx.RequestError as error:
            raise LLMPlannerError("AI planner request could not be completed") from error
        if response.status_code >= 400:
            raise LLMPlannerError(
                f"AI planner request failed with status {response.status_code}: {response.text[:500]}"
            )
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            plan = SearchPlan.model_validate(self._decode_json(content))
            return self.validator.validate(plan)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMPlannerError("AI planner returned an invalid response") from error
        except PlanValidationError as error:
            raise LLMPlannerError(str(error)) from error

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    @staticmethod
    def _decode_json(content: Any) -> dict[str, Any]:
        if not isinstance(content, str):
            raise TypeError("planner content must be a string")
        cleaned = content.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
        if fenced:
            cleaned = fenced.group(1)
        decoded = json.loads(cleaned)
        if not isinstance(decoded, dict):
            raise ValueError("planner response must be a JSON object")
        return decoded
