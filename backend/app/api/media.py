"""Media ingestion endpoints.

Accepts media payloads that have been authorised by external rights checks,
validates integrity, stores in MinIO, and persists asset/rights records.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import MediaAsset, MediaRight, Video
from app.db.session import get_session
from app.media.providers import MediaIngestionResult, MediaRights, MinIOProvider

router = APIRouter(prefix="/media", tags=["media"])


class MediaRightsRequest(BaseModel):
    rights_holder: str = Field(min_length=1, max_length=255)
    permission_scope: str = Field(min_length=1)
    evidence_uri: str = Field(min_length=1, max_length=2048)


@router.post("/ingest")
async def ingest_media(
    video_id: str = Form(...),
    file: UploadFile = File(...),
    rights_holder: str = Form(...),
    permission_scope: str = Form(...),
    evidence_uri: str = Form(...),
    expected_checksum: str | None = Form(None),
    expected_duration: int | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Ingest an authorised media file for a video."""
    try:
        video_uuid = UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid video_id format")

    video = await session.get(Video, video_uuid)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    settings = get_settings()
    provider = MinIOProvider()

    content = await file.read()
    file_size = len(content)

    rights = MediaRights(
        rights_holder=rights_holder,
        permission_scope=permission_scope,
        evidence_uri=evidence_uri,
        verified_at=None,
    )

    from io import BytesIO
    result: MediaIngestionResult = await provider.ingest(
        video_id=video_uuid,
        stream=BytesIO(content),
        file_size=file_size,
        rights=rights,
        expected_checksum=expected_checksum,
        expected_duration=expected_duration,
        content_type=file.content_type,
    )

    if not result.success:
        asset = MediaAsset(
            video_id=video_uuid,
            status="rejected",
            object_key=None,
            checksum_sha256=None,
            file_size_bytes=None,
            duration_seconds=None,
        )
        session.add(asset)
        await session.commit()
        raise HTTPException(status_code=422, detail=result.error)

    # Persist MediaAsset
    asset = MediaAsset(
        video_id=video_uuid,
        status="stored",
        object_key=result.object_key,
        checksum_sha256=result.checksum_sha256,
        file_size_bytes=result.file_size_bytes,
        duration_seconds=result.duration_seconds,
    )
    session.add(asset)

    # Persist MediaRight
    right = MediaRight(
        asset_id=asset.id,
        rights_holder=rights.rights_holder,
        permission_scope=rights.permission_scope,
        evidence_uri=rights.evidence_uri,
        verified_at=None,
    )
    session.add(right)

    # Update video media_status
    video.media_status = "stored"
    await session.commit()
    await session.refresh(asset)

    return {
        "asset_id": str(asset.id),
        "video_id": video_id,
        "status": "stored",
        "object_key": result.object_key,
        "checksum_sha256": result.checksum_sha256,
        "file_size_bytes": result.file_size_bytes,
        "duration_seconds": result.duration_seconds,
        "content_type": result.content_type,
    }


@router.get("/assets/{asset_id}")
async def get_media_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Retrieve media asset metadata."""
    try:
        asset_uuid = UUID(asset_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid asset_id format")

    asset = await session.get(MediaAsset, asset_uuid)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")

    rights = [
        {
            "rights_holder": r.rights_holder,
            "permission_scope": r.permission_scope,
            "evidence_uri": r.evidence_uri,
            "verified_at": r.verified_at.isoformat() if r.verified_at else None,
        }
        for r in asset.rights
    ]

    return {
        "asset_id": str(asset.id),
        "video_id": str(asset.video_id),
        "status": asset.status.value if hasattr(asset.status, "value") else str(asset.status),
        "object_key": asset.object_key,
        "checksum_sha256": asset.checksum_sha256,
        "file_size_bytes": asset.file_size_bytes,
        "duration_seconds": asset.duration_seconds,
        "rights": rights,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }