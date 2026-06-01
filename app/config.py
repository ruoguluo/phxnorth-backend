"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application settings
    app_name: str = "PhxNorth Backend"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Security settings
    secret_key: str = "phxnorth-dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/phxnorth"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kafka
    kafka_bootstrap_servers: List[str] = ["localhost:9092"]

    # API
    api_prefix: str = "/api/v1"

    # S3
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # LLM (DeepSeek for CV parsing fallback)
    deepseek_api_key: str = ""
    llm_cv_parser_enabled: bool = True
    llm_question_assist_enabled: bool = True
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"

    # Webhooks
    webhook_timeout: int = 10
    webhook_max_retries: int = 5

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() == "testing"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
