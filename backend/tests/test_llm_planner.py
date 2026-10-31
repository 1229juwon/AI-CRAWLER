import httpx
import pytest

from app.agent.llm import LLMPlannerError, OpenAICompatiblePlanner


def make_response(request: httpx.Request, payload: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code, json=payload, request=request)


@pytest.mark.asyncio
async def test_openai_compatible_planner_validates_json_and_auth_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-api-key"
        assert request.headers["authorization"] == "Bearer test-jwt"
        body = request.read().decode()
        assert '"model":"test-model"' in body
        return make_response(
            request,
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "```json\n"
                                '{"request_text":"find safety videos","platform":"youtube",'
                                '"queries":["product safety"],"order":"date","page_size":10,'
                                '"collect_comments":false,"collect_captions":false}\n'
                                "```"
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    planner = OpenAICompatiblePlanner(
        endpoint="http://test.local/chat/completions",
        model="test-model",
        api_key="test-api-key",
        jwt_token="test-jwt",
        http_client=client,
    )
    plan = await planner.create_plan("Find safety videos")

    assert plan.queries == ["product safety"]
    assert plan.order.value == "date"
    await planner.aclose()


@pytest.mark.asyncio
async def test_planner_rejects_malformed_model_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return make_response(request, {"choices": [{"message": {"content": "not json"}}]})

    planner = OpenAICompatiblePlanner(
        endpoint="http://test.local/chat/completions",
        model="test-model",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMPlannerError, match="invalid response"):
        await planner.create_plan("Find safety videos")
    await planner.aclose()
