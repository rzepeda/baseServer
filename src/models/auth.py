from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, SecretStr, validator


class AuthContext:
    """
    Purpose: OAuth token validation result, attached to authenticated requests
    """

    def __init__(
        self,
        is_valid: bool,
        token_hash: str,
        scopes: list[str],
        expires_at: datetime | None,
        client_id: str | None,
    ):
        self.is_valid = is_valid
        self.token_hash = token_hash
        self.scopes = scopes
        self.expires_at = expires_at
        self.client_id = client_id

    def to_dict(self) -> dict[str, Any]:
        """Serializes the object to a dictionary."""
        return {
            "is_valid": self.is_valid,
            "token_hash": self.token_hash,
            "scopes": self.scopes,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "client_id": self.client_id,
        }



class OAuthConfig(BaseModel):
    """
    OAuth configuration settings loaded from environment variables.
    Uses pydantic for validation.
    """

    provider_url: HttpUrl = Field(
        ...,
        description="Base URL of the OAuth provider, e.g., https://oauth.example.com",
    )
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: SecretStr = Field(..., description="OAuth client secret")
    scopes: list[str] = Field(
        ...,
        description="List of authorized scopes, e.g., ['read:transcripts']",
    )
    validation_endpoint: HttpUrl = Field(..., description="URL for the token validation endpoint")

    @validator("scopes", pre=True)
    def parse_scopes(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [scope.strip() for scope in v.split(",") if scope.strip()]
        return []
