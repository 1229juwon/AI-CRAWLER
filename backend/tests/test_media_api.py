"""Tests for the media ingestion API endpoints."""

import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.media.providers import MediaIngestionResult


@pytest.fixture
def client():
    return TestClient(app)


class TestMediaIngestionAPI:
    """Test media ingestion endpoints."""

    @pytest.mark.asyncio
    async def test_ingest_rejects_invalid_video_id(self, client):
        """Invalid video_id format should return 422."""
        response = client.post(
            "/media/ingest",
            data={
                "video_id": "not-a-uuid",
                "rights_holder": "Test Corp",
                "permission_scope": "streaming",
                "evidence_uri": "https://example.com/license",
            },
            files={"file": ("test.mp4", b"content")},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_rejects_unknown_video(self, client):
        """Ingesting for a non-existent video should return 404."""
        fake_uuid = str(uuid4())
        with patch("app.api.media.MinIOProvider") as mock_provider_cls:
            mock_provider = MagicMock()
            mock_provider.ingest = MagicMock(
                return_value=MediaIngestionResult(
                    success=True,
                    object_key=f"videos/{fake_uuid}/abc123",
                    checksum_sha256="abc123",
                    file_size_bytes=7,
                )
            )
            mock_provider_cls.return_value = mock_provider

            response = client.post(
                "/media/ingest",
                data={
                    "video_id": fake_uuid,
                    "rights_holder": "Test Corp",
                    "permission_scope": "streaming",
                    "evidence_uri": "https://example.com/license",
                },
                files={"file": ("test.mp4", b"content")},
            )
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_ingest_rejects_unauthorised_media(self, client):
        """Missing rights_holder should return 422 with rejection."""
        engine, session_factory = await self._postgres_session()
        async with session_factory() as session:
            from app.db.models import Video, PlatformSource
            source = PlatformSource(platform="youtube", display_name="YouTube", base_url="https://www.youtube.com")
            session.add(source)
            await session.flush()
            video = Video(source_id=source.id, platform_video_id="test-video-1", title="Test")
            session.add(video)
            await session.commit()
            video_id = str(video.id)

        response = client.post(
            "/media/ingest",
            data={
                "video_id": video_id,
                "rights_holder": "",
                "permission_scope": "streaming",
                "evidence_uri": "https://example.com/license",
            },
            files={"file": ("test.mp4", b"content")},
        )
        assert response.status_code == 422
        body = response.json()
        assert "detail" in body

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_get_media_asset_returns_404(self, client):
        """Non-existent asset should return 404."""
        fake_uuid = str(uuid4())
        response = client.get(f"/media/assets/{fake_uuid}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_media_asset_rejects_invalid_id(self, client):
        """Invalid asset_id format should return 422."""
        response = client.get("/media/assets/not-a-uuid")
        assert response.status_code == 422

    @staticmethod
    async def _postgres_session():
        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://crawler:crawler@localhost:5432/crawler")
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as error:
            await engine.dispose()
            pytest.skip(f"PostgreSQL integration database unavailable: {error}")
        return engine, async_sessionmaker(engine, expire_on_commit=False)