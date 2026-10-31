import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    waiting_quota = "waiting_quota"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class VideoMetadataStatus(str, enum.Enum):
    discovered = "discovered"
    collected = "collected"
    failed = "failed"


class MediaStatus(str, enum.Enum):
    not_requested = "not_requested"
    permission_pending = "permission_pending"
    queued = "queued"
    stored = "stored"
    rejected = "rejected"
    failed = "failed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CollectionJob(TimestampMixin, Base):
    __tablename__ = "collection_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_text: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"), default=JobStatus.pending)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    tasks: Mapped[list["CollectionTask"]] = relationship(back_populates="job")
    agent_executions: Mapped[list["AgentExecution"]] = relationship(back_populates="job")


class CollectionTask(TimestampMixin, Base):
    __tablename__ = "collection_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_jobs.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(50))
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), default=TaskStatus.pending)
    error_message: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True)

    job: Mapped[CollectionJob] = relationship(back_populates="tasks")
    keywords: Mapped[list["CollectionKeyword"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class CollectionKeyword(Base):
    __tablename__ = "collection_keywords"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_tasks.id", ondelete="CASCADE"))
    keyword: Mapped[str] = mapped_column(String(500))

    task: Mapped[CollectionTask] = relationship(back_populates="keywords")
    __table_args__ = (UniqueConstraint("task_id", "keyword", name="uq_task_keyword"),)


class PlatformSource(Base):
    __tablename__ = "platform_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))

    videos: Mapped[list["Video"]] = relationship(back_populates="source")


class Video(TimestampMixin, Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_sources.id"))
    platform_video_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(Text)
    channel_name: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int | None] = mapped_column(Integer)
    metadata_status: Mapped[VideoMetadataStatus] = mapped_column(
        Enum(VideoMetadataStatus, name="video_metadata_status"), default=VideoMetadataStatus.discovered
    )
    media_status: Mapped[MediaStatus] = mapped_column(
        Enum(MediaStatus, name="media_status"), default=MediaStatus.not_requested
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    source: Mapped[PlatformSource] = relationship(back_populates="videos")
    comments: Mapped[list["VideoComment"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    captions: Mapped[list["VideoCaption"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    media_assets: Mapped[list["MediaAsset"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    __table_args__ = (
        UniqueConstraint("source_id", "platform_video_id", name="uq_video_platform_id"),
        Index("ix_videos_metadata_status", "metadata_status"),
        Index("ix_videos_media_status", "media_status"),
    )


class VideoComment(Base):
    __tablename__ = "video_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    platform_comment_id: Mapped[str] = mapped_column(String(255))
    author_name: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    video: Mapped[Video] = relationship(back_populates="comments")
    __table_args__ = (UniqueConstraint("video_id", "platform_comment_id", name="uq_video_comment"),)


class VideoCaption(Base):
    __tablename__ = "video_captions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(50))
    has_access: Mapped[bool] = mapped_column(default=False)
    object_key: Mapped[str | None] = mapped_column(String(1024))
    video: Mapped[Video] = relationship(back_populates="captions")


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    status: Mapped[MediaStatus] = mapped_column(Enum(MediaStatus, name="media_status"), default=MediaStatus.not_requested)
    object_key: Mapped[str | None] = mapped_column(String(1024))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    video: Mapped[Video] = relationship(back_populates="media_assets")
    rights: Mapped[list["MediaRight"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class MediaRight(TimestampMixin, Base):
    __tablename__ = "media_rights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    rights_holder: Mapped[str] = mapped_column(String(255))
    permission_scope: Mapped[str] = mapped_column(Text)
    evidence_uri: Mapped[str] = mapped_column(String(2048))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    asset: Mapped[MediaAsset] = relationship(back_populates="rights")


class CollectionLog(Base):
    __tablename__ = "collection_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("collection_jobs.id", ondelete="SET NULL"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("collection_tasks.id", ondelete="SET NULL"))
    level: Mapped[str] = mapped_column(String(20))
    event_type: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(50))
    api_name: Mapped[str] = mapped_column(String(100))
    quota_cost: Mapped[int] = mapped_column(Integer)
    quota_remaining: Mapped[int | None] = mapped_column(Integer)
    response_status: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentExecution(TimestampMixin, Base):
    __tablename__ = "agent_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("collection_jobs.id", ondelete="SET NULL"))
    request_text: Mapped[str] = mapped_column(Text)
    plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    tools_called: Mapped[list] = mapped_column(JSONB, default=list)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    job: Mapped[CollectionJob | None] = relationship(back_populates="agent_executions")
