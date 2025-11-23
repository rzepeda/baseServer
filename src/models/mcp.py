"""Models for the MCP server."""

from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional

import structlog
from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """
    Defines the structure for an MCP tool's metadata, used for schema generation.
    """
    name: str = Field(..., description="The unique name of the tool.")
    description: str = Field(..., description="A brief description of what the tool does.")
    input_schema: Dict[str, Any] = Field(..., description="The JSON schema for the tool's input parameters.")
    version: str = Field("1.0", description="The version of the tool definition.")


@dataclass
class ToolExecutionContext:
    """
    Context object passed to tool handlers.
    Encapsulates request-specific information like correlation ID, logger, and auth context.
    """
    correlation_id: str
    logger: structlog.stdlib.BoundLogger
    auth_context: Optional[Dict[str, Any]] = None
    start_time: float = Field(default_factory=datetime.now().timestamp)


class HealthCheckResponse(BaseModel):
    """
    Response model for the health check endpoint.
    """

    status: str = Field(..., description="Status of the server")
    version: str = Field(..., description="Version of the server")
    timestamp: datetime = Field(..., description="Current server timestamp in ISO 8601 format")
    tools_loaded: int = Field(..., description="Number of tools currently loaded")
    registered_tools: list[str] = Field(default_factory=list, description="List of registered tool names")
