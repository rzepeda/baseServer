"""Authentication data models."""

from typing import Optional

from pydantic import BaseModel, Field


class AuthContext(BaseModel):
    """Authentication context attached to requests."""

    user_id: str = Field(..., description="Authenticated user ID")
    token: str = Field(..., description="OAuth bearer token")
    scopes: list[str] = Field(
        default_factory=list, description="OAuth token scopes"
    )
    client_id: Optional[str] = Field(None, description="OAuth client ID")

    class Config:
        """Pydantic configuration."""

        frozen = True  # Immutable after creation
