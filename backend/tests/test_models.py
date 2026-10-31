from app.db import models  # noqa: F401
from app.db.base import Base


def test_required_tables_are_registered() -> None:
    expected = {
        "collection_jobs",
        "collection_tasks",
        "collection_keywords",
        "platform_sources",
        "videos",
        "video_comments",
        "video_captions",
        "media_assets",
        "media_rights",
        "collection_logs",
        "api_usage_logs",
        "agent_executions",
    }
    assert expected.issubset(Base.metadata.tables)
