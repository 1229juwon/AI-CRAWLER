from fastapi.testclient import TestClient

from app.main import app


def test_validate_agent_plan() -> None:
    response = TestClient(app).post(
        "/agent/plans/validate",
        json={
            "plan": {
                "request_text": "recent safety videos",
                "queries": ["product safety", "child safety"],
                "collect_comments": False,
                "collect_captions": False,
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["tools"] == ["youtube.search", "youtube.get_metadata"]


def test_validate_agent_plan_rejects_blank_query() -> None:
    response = TestClient(app).post(
        "/agent/plans/validate",
        json={
            "plan": {
                "request_text": "recent safety videos",
                "queries": [" "],
            }
        },
    )

    assert response.status_code == 422
    assert "must not be blank" in response.json()["detail"]
