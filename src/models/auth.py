"""Authentication data models."""


from pydantic import BaseModel, ConfigDict, Field


class AuthContext(BaseModel):
    """Authentication context attached to requests."""

    user_id: str = Field(..., description="Authenticated user ID")
    token: str = Field(..., description="OAuth bearer token")
    scopes: list[str] = Field(
        default_factory=list, description="OAuth token scopes"
    )
    client_id: str | None = Field(None, description="OAuth client ID")

    model_config = ConfigDict(frozen=True)  # Immutable after creation
