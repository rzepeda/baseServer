"""Configuration management using environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server Configuration
    server_host: str = Field(default="0.0.0.0", description="Server bind address")
    server_port: int = Field(default=8000, description="Server port", ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    environment: str = Field(default="development", description="Environment name")

    # OAuth Configuration
    oauth_issuer_url: str = Field(
        ..., description="OAuth issuer URL for token validation"
    )
    oauth_audience: str = Field(..., description="Expected OAuth audience")
    oauth_token_cache_ttl: int = Field(
        default=60, description="OAuth token cache TTL in seconds", ge=0
    )


@lru_cache()
def get_config() -> Config:
    """Get cached configuration instance."""
    return Config()
