from datetime import datetime

from pydantic import BaseModel, Field, SecretStr


class AuthContext(BaseModel):
    """
    Pydantic model for the OAuth token validation result, attached to authenticated requests.
    """

    is_valid: bool
    token_hash: str
    scopes: list[str]
    expires_at: datetime | None
    client_id: str | None
    user_id: str | None = Field(None, description="Subject identifier for the user")


class OAuthConfig(BaseModel):
    """OAuth configuration model for provider settings."""

    provider_url: str
    client_id: str
    client_secret: SecretStr
    scopes: list[str] | str
    validation_endpoint: str
