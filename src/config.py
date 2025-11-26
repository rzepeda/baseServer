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
    mcp_port: int = Field(default=8080, description="MCP Server port", ge=1, le=65535)
    rest_api_port: int = Field(default=8081, description="REST API Server port", ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )
    environment: str = Field(default="development", description="Environment name")

    # Cloudflare Tunnel Configuration
    cloudflare_tunnel_url: str = Field(
        default="https://agentictools.uk",
        description="Cloudflare Tunnel URL for external access to the MCP server",
    )

    # OAuth Configuration (optional for minimal server mode)
    oauth_issuer_url: str = Field(default="", description="OAuth issuer URL for token validation")
    oauth_audience: str = Field(default="", description="Expected OAuth audience")
    oauth_token_cache_ttl: int = Field(
        default=60, description="OAuth token cache TTL in seconds", ge=0
    )

    # Minimal Server Mode (for debugging/PoC)
    use_minimal_server: bool = Field(
        default=False, description="Use minimal MCP server instead of full server"
    )


@lru_cache
def get_config() -> Config:
    """Get cached configuration instance."""
    return Config()
