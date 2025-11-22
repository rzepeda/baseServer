"""MCP protocol data models."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MCPToolInvocation(BaseModel):
    """MCP tool invocation request."""

    tool_name: str = Field(..., description="Name of the tool to invoke")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Tool parameters"
    )
    correlation_id: Optional[str] = Field(
        None, description="Request correlation ID for tracing"
    )


class MCPToolResponse(BaseModel):
    """MCP tool invocation response."""

    success: bool = Field(..., description="Whether the tool executed successfully")
    result: Optional[Any] = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    correlation_id: Optional[str] = Field(
        None, description="Request correlation ID for tracing"
    )


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Server version")
    tools_loaded: int = Field(..., description="Number of tools loaded")
