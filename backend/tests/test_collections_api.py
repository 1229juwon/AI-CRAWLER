from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_create_collection_enqueues_youtube_task() -> None:
    with patch("app.api.collections.collect_youtube.apply_async") as enqueue:
        enqueue.return_value = SimpleNamespace(id=str(uuid4()))
        response = TestClient(app).post(
            "/collection-jobs",
            json={"request_text": "recent safety videos", "query": "product safety"},
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    enqueue.assert_called_once()
