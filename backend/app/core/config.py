"""Application configuration, loaded from the environment once at import time."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application -------------------------------------------------------
    app_env: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # --- Database ----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://alma:alma@localhost:5432/alma"
    db_echo: bool = False

    # --- Auth --------------------------------------------------------------
    jwt_secret: str = "dev-secret-change-me-0123456789abcdef0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- Seed account ------------------------------------------------------
    seed_admin_email: str = "attorney@example.com"
    seed_admin_password: str = "changeme123"
    seed_admin_name: str = "Alma Attorney"

    # --- Storage -----------------------------------------------------------
    storage_backend: Literal["s3", "local"] = "s3"
    s3_bucket: str = "alma-resumes"
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    local_storage_dir: str = "/var/lib/alma/resumes"
    presigned_url_ttl_seconds: int = 300

    max_resume_size_bytes: int = 5 * 1024 * 1024

    # --- Email -------------------------------------------------------------
    email_backend: Literal["smtp", "console"] = "smtp"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False
    smtp_timeout_seconds: int = 10
    email_from: str = "no-reply@example.com"
    email_from_name: str = "Alma"
    attorney_notification_email: str = "attorney@example.com"

    # --- URLs --------------------------------------------------------------
    internal_app_base_url: str = "http://localhost:3000"

    # Kept as a raw string: pydantic-settings tries to JSON-decode any complex
    # field straight from the environment, which rejects a plain
    # comma-separated CORS_ORIGINS before a validator ever sees it. The parsed
    # list is exposed by the `cors_origins` property below.
    cors_origins_raw: str = Field(
        default="http://localhost:3000",
        validation_alias="CORS_ORIGINS",
    )

    # --- Rate limiting -----------------------------------------------------
    public_submit_rate_limit: int = 10          # requests per window per IP
    public_submit_rate_window_seconds: int = 60

    @property
    def cors_origins(self) -> list[str]:
        """Allowed browser origins, from a comma-separated CORS_ORIGINS."""
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
