"""Base media provider contract and MinIO-backed implementation.

MediaProvider receives media payloads that have already been authorised
through external rights checks.  It validates file integrity (size, duration,
SHA-256), stores authorised content in MinIO, and rejects anything that fails
permission or integrity checks.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class MediaValidationError(RuntimeError):
    """Raised when a media payload fails permission or integrity checks."""


@dataclass(frozen=True)
class MediaRights:
    """Evidence that the caller is authorised to store this media."""

    rights_holder: str
    permission_scope: str
    evidence_uri: str
    verified_at: datetime | None = None


@dataclass(frozen=True)
class MediaIngestionResult:
    """Outcome of attempting to ingest a media payload."""

    success: bool
    object_key: str | None = None
    checksum_sha256: str | None = None
    file_size_bytes: int | None = None
    duration_seconds: int | None = None
    content_type: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class BaseMediaProvider:
    """Contract for receiving, validating, and storing media assets."""

    async def ingest(
        self,
        video_id: uuid.UUID,
        stream: BinaryIO,
        file_size: int,
        rights: MediaRights,
        expected_checksum: str | None = None,
        expected_duration: int | None = None,
        content_type: str | None = None,
    ) -> MediaIngestionResult:
        """Validate permissions and integrity, then store the media.

        Parameters
        ----------
        video_id:
            Associated video record identifier.
        stream:
            Binary stream of the media file.
        file_size:
            Expected file size in bytes.
        rights:
            Authorisation evidence for this media.
        expected_checksum:
            Optional SHA-256 hex digest to verify against.
        expected_duration:
            Optional duration in seconds to verify against.
        content_type:
            MIME type hint for storage metadata.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# MinIO-backed provider
# ---------------------------------------------------------------------------


class MinIOProvider(BaseMediaProvider):
    """Store authorised media in MinIO with integrity verification."""

    def __init__(self, client: Minio | None = None) -> None:
        settings = get_settings()
        self._client: Minio = client or Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key.get_secret_value(),
            secure=settings.minio_secure,
        )
        self._bucket: str = settings.minio_bucket

    async def ingest(
        self,
        video_id: uuid.UUID,
        stream: BinaryIO,
        file_size: int,
        rights: MediaRights,
        expected_checksum: str | None = None,
        expected_duration: int | None = None,
        content_type: str | None = None,
    ) -> MediaIngestionResult:
        # 1. Permission check — reject unauthorised input
        if not rights or not rights.rights_holder or not rights.evidence_uri:
            return MediaIngestionResult(
                success=False,
                error="MediaRights evidence is required: rights_holder and evidence_uri must be provided.",
            )

        # 2. Read the entire stream and compute checksum
        stream.seek(0)
        data = stream.read()
        actual_size = len(data)

        if actual_size != file_size:
            return MediaIngestionResult(
                success=False,
                error=f"Size mismatch: expected {file_size} bytes, got {actual_size}.",
            )

        sha256 = hashlib.sha256(data).hexdigest()

        if expected_checksum and sha256 != expected_checksum:
            return MediaIngestionResult(
                success=False,
                error=f"Checksum mismatch: expected {expected_checksum}, got {sha256}.",
            )

        # 3. Determine content type
        mime = content_type or mimetypes.guess_type("media.mp4")[0] or "application/octet-stream"

        # 4. Build object key
        object_key = f"videos/{video_id}/{sha256}"

        # 5. Upload to MinIO
        try:
            self._client.put_object(
                bucket_name=self._bucket,
                object_name=object_key,
                data=BytesIO(data),
                length=actual_size,
                content_type=mime,
            )
        except S3Error as exc:
            logger.error("MinIO upload failed for %s: %s", object_key, exc)
            return MediaIngestionResult(
                success=False,
                error=f"MinIO upload failed: {exc}",
            )

        logger.info(
            "Stored media %s (%d bytes, sha256=%s) in %s",
            object_key,
            actual_size,
            sha256,
            self._bucket,
        )

        return MediaIngestionResult(
            success=True,
            object_key=object_key,
            checksum_sha256=sha256,
            file_size_bytes=actual_size,
            duration_seconds=expected_duration,
            content_type=mime,
        )