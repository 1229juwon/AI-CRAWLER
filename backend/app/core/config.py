from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Crawler API"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "******localhost:5432/crawler"
    redis_url: str = "redis://localhost:6379/0"
    youtube_api_key: SecretStr = Field(default=SecretStr(""))
    youtube_api_key_sub: SecretStr = Field(default=SecretStr(""))
    youtube_daily_quota: int = 10000
    ai_api_url: str = "http://localhost:8088/api/chat/completions"
    ai_api_key: SecretStr = Field(default=SecretStr(""))
    ai_jwt_token: SecretStr = Field(default=SecretStr(""))
    ai_model: str = "gemma-4-26B-A4B-it"
    ai_request_timeout_seconds: float = 30.0
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "crawler"
    minio_secret_key: SecretStr = Field(default=SecretStr("crawler-secret"))
    minio_bucket: str = "media"
    minio_secure: bool = False

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        if value not in allowed:
            raise ValueError(f"environment must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("log_level must be a standard Python logging level")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()