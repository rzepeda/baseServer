"""Configuration management using environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.models.auth import OAuthConfig


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
        default="https://frequently-introducing-segment-keep.trycloudflare.com/mcp",
        description="Cloudflare Tunnel URL for external access to the MCP server",
    )

    # OAuth Configuration for Middleware
    oauth_provider_url: str = Field(..., description="OAuth provider base URL for token validation")
    oauth_client_id: str = Field(..., description="OAuth client ID")
    oauth_client_secret: SecretStr = Field(..., description="OAuth client secret")
    oauth_scopes: str = Field(..., description="Comma-separated list of authorized OAuth scopes")
    oauth_validation_endpoint: str = Field(..., description="URL for the token validation endpoint")
    oauth_token_cache_ttl: int = Field(
        default=60, description="OAuth token cache TTL in seconds", ge=0
    )

    @property
    def oauth_config(self) -> OAuthConfig:
        """Returns an instance of OAuthConfig for easy access and validation."""
        return OAuthConfig(
            provider_url=self.oauth_provider_url,
            client_id=self.oauth_client_id,
            client_secret=self.oauth_client_secret,
            scopes=self.oauth_scopes,
            validation_endpoint=self.oauth_validation_endpoint,
        )


@lru_cache
def get_config() -> Config:
    """Get cached configuration instance."""
    return Config()
