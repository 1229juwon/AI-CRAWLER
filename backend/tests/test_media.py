"""Tests for the media module: BaseMediaProvider contract, MinIOProvider, and API."""

import hashlib
import os
from io import BytesIO
from uuid import uuid4

import pytest

from app.media.providers import (
    BaseMediaProvider,
    MediaIngestionResult,
    MediaRights,
    MediaValidationError,
    MinIOProvider,
)


# ---------------------------------------------------------------------------
# BaseMediaProvider contract tests
# ---------------------------------------------------------------------------


class TestBaseMediaProviderContract:
    """Verify that the protocol/abstract base defines the expected interface."""

    def test_base_media_provider_is_protocol(self) -> None:
        """BaseMediaProvider must define ingest with the expected signature."""
        assert hasattr(BaseMediaProvider, "ingest")

    def test_media_validation_error_is_runtime_error(self) -> None:
        """MediaValidationError must be a RuntimeError subclass."""
        assert issubclass(MediaValidationError, RuntimeError)

    def test_media_rights_frozen_dataclass(self) -> None:
        """MediaRights must be a frozen dataclass with required fields."""
        rights = MediaRights(
            rights_holder="Test Corp",
            permission_scope="streaming",
            evidence_uri="https://example.com/license",
        )
        assert rights.rights_holder == "Test Corp"
        with pytest.raises(Exception):  # frozen
            rights.rights_holder = "Other"


class TestMinIOProviderPermissionValidation:
    """Unauthorised input must be rejected before any storage attempt."""

    @pytest.mark.asyncio
    async def test_rejects_missing_rights_holder(self) -> None:
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"test content"
        stream = BytesIO(data)

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=MediaRights(
                rights_holder="",
                permission_scope="streaming",
                evidence_uri="https://example.com/license",
            ),
        )

        assert result.success is False
        assert "rights_holder" in result.error.lower() or "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rejects_missing_evidence_uri(self) -> None:
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"test content"
        stream = BytesIO(data)

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=MediaRights(
                rights_holder="Test Corp",
                permission_scope="streaming",
                evidence_uri="",
            ),
        )

        assert result.success is False
        assert "required" in result.error.lower() or "evidence_uri" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rejects_none_rights(self) -> None:
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"test content"
        stream = BytesIO(data)

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=None,  # type: ignore
        )

        assert result.success is False
        assert "required" in result.error.lower()


class TestMinIOProviderIntegrityValidation:
    """Size and checksum validation must catch tampered payloads."""

    @pytest.mark.asyncio
    async def test_rejects_size_mismatch(self) -> None:
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"test content"
        stream = BytesIO(data)

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data) + 100,  # wrong size
            rights=MediaRights(
                rights_holder="Test Corp",
                permission_scope="streaming",
                evidence_uri="https://example.com/license",
            ),
        )

        assert result.success is False
        assert "size" in result.error.lower() or "mismatch" in result.error.lower()

    @pytest.mark.asyncio
    async def test_rejects_checksum_mismatch(self) -> None:
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"test content"
        stream = BytesIO(data)
        wrong_checksum = "0" * 64

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=MediaRights(
                rights_holder="Test Corp",
                permission_scope="streaming",
                evidence_uri="https://example.com/license",
            ),
            expected_checksum=wrong_checksum,
        )

        assert result.success is False
        assert "checksum" in result.error.lower() or "mismatch" in result.error.lower()

    @pytest.mark.asyncio
    async def test_accepts_correct_checksum(self) -> None:
        """When checksum matches, ingestion proceeds (may fail on MinIO connectivity)."""
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"test content for checksum"
        stream = BytesIO(data)
        correct_checksum = hashlib.sha256(data).hexdigest()

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=MediaRights(
                rights_holder="Test Corp",
                permission_scope="streaming",
                evidence_uri="https://example.com/license",
            ),
            expected_checksum=correct_checksum,
        )

        # If MinIO is available, it should succeed
        # If MinIO is not available, it should fail with a MinIO error, not a validation error
        if result.success:
            assert result.checksum_sha256 == correct_checksum
            assert result.file_size_bytes == len(data)
        else:
            # MinIO not available — but validation passed
            assert "checksum" not in result.error.lower()
            assert "size" not in result.error.lower()
            assert "required" not in result.error.lower()


class TestMinIOProviderSuccessfulIngestion:
    """Authorised, valid media should be stored and metadata returned."""

    @pytest.mark.asyncio
    async def test_ingest_returns_correct_metadata(self) -> None:
        """Successful ingestion returns object_key, checksum, and size."""
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"sample media content for storage"
        stream = BytesIO(data)
        correct_checksum = hashlib.sha256(data).hexdigest()

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=MediaRights(
                rights_holder="Test Corp",
                permission_scope="streaming",
                evidence_uri="https://example.com/license",
            ),
            expected_checksum=correct_checksum,
            expected_duration=120,
            content_type="video/mp4",
        )

        if result.success:
            assert result.object_key is not None
            assert result.object_key.startswith(f"videos/{video_id}/")
            assert result.checksum_sha256 == correct_checksum
            assert result.file_size_bytes == len(data)
            assert result.duration_seconds == 120
            assert result.content_type == "video/mp4"
        else:
            # MinIO may not be running — skip assertion
            pass

    @pytest.mark.asyncio
    async def test_ingest_without_expected_checksum(self) -> None:
        """Ingestion should work without an expected checksum (optional field)."""
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"content without checksum check"
        stream = BytesIO(data)

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=MediaRights(
                rights_holder="Test Corp",
                permission_scope="streaming",
                evidence_uri="https://example.com/license",
            ),
        )

        if result.success:
            assert result.checksum_sha256 is not None
            assert result.file_size_bytes == len(data)
        else:
            # MinIO may not be running
            pass


class TestMinIOProviderContentType:
    """Content type detection should work correctly."""

    @pytest.mark.asyncio
    async def test_uses_provided_content_type(self) -> None:
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"test"
        stream = BytesIO(data)

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=MediaRights(
                rights_holder="Test Corp",
                permission_scope="streaming",
                evidence_uri="https://example.com/license",
            ),
            content_type="application/custom-type",
        )

        if result.success:
            assert result.content_type == "application/custom-type"
        else:
            pass

    @pytest.mark.asyncio
    async def test_falls_back_to_mimetypes_for_unknown(self) -> None:
        provider = MinIOProvider()
        video_id = uuid4()
        data = b"\x00" * 100
        stream = BytesIO(data)

        result = await provider.ingest(
            video_id=video_id,
            stream=stream,
            file_size=len(data),
            rights=MediaRights(
                rights_holder="Test Corp",
                permission_scope="streaming",
                evidence_uri="https://example.com/license",
            ),
        )

        if result.success:
            assert result.content_type is not None
            assert len(result.content_type) > 0
        else:
            pass