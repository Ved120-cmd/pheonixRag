"""Centralized application configuration using Pydantic Settings.

All environment-driven configuration flows through this single, typed,
validated object instead of scattered os.getenv() calls throughout the
codebase.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "PhoenixRAG"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    api_port: int = 8000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- PostgreSQL ---
    postgres_user: str = "phoenix"
    postgres_password: str = "phoenix"
    postgres_db: str = "phoenixrag"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    raw_database_url: str | None = Field(default=None, alias="DATABASE_URL")
    raw_database_url_sync: str | None = Field(default=None, alias="DATABASE_URL_SYNC")

    @property
    def database_url(self) -> str:
        if self.raw_database_url:
            return self.raw_database_url
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def database_url_sync(self) -> str:
        if self.raw_database_url_sync:
            return self.raw_database_url_sync
        return f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # --- Redis ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = "phoenix"
    redis_db: int = 0
    raw_redis_url: str | None = Field(default=None, alias="REDIS_URL")

    @property
    def redis_url(self) -> str:
        if self.raw_redis_url:
            return self.raw_redis_url
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # --- Qdrant ---
    qdrant_host: str = "localhost"
    qdrant_http_port: int = 6333
    qdrant_grpc_port: int = 6334
    raw_qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")

    @property
    def qdrant_url(self) -> str:
        if self.raw_qdrant_url:
            return self.raw_qdrant_url
        return f"http://{self.qdrant_host}:{self.qdrant_http_port}"

    # --- MinIO ---
    minio_root_user: str = "phoenix"
    minio_root_password: str = "phoenix123"
    minio_api_port: int = 9000
    minio_console_port: int = 9091
    minio_host: str = "localhost"
    raw_minio_endpoint: str | None = Field(default=None, alias="MINIO_ENDPOINT")
    minio_secure: bool = False
    minio_bucket: str = "phoenixrag"

    @property
    def minio_endpoint(self) -> str:
        if self.raw_minio_endpoint:
            return self.raw_minio_endpoint
        return f"{self.minio_host}:{self.minio_api_port}"


    # --- Ollama (container only, no integration in Phase 1) ---
    ollama_port: int = 11434
    ollama_host: str = "ollama"
    ollama_url: str = "http://ollama:11434"

    # --- Security ---
    secret_key: str = Field(default="change-me-to-a-random-64-char-string-in-production")

    # --- JWT / IAM ---
    jwt_secret_key: str = Field(default="change-me-jwt-secret-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    password_reset_token_expire_minutes: int = 30
    email_verification_token_expire_hours: int = 24

    # --- Auth security hooks ---
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 300
    account_lockout_threshold: int = 5
    account_lockout_duration_seconds: int = 900

    # --- Frontend (for email links in mock service) ---
    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # --- Bootstrap admin (created by seed_iam if not exists) ---
    bootstrap_admin_email: str = "admin@phoenixrag.local"
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = Field(default="ChangeMe!Admin1")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor.

    lru_cache ensures the .env file / environment is parsed exactly once
    per process, and the same Settings instance is reused everywhere via
    FastAPI dependency injection.
    """
    return Settings()
