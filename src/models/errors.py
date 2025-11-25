"""Error handling data models."""

from typing import Any
from enum import Enum

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Standardized error codes."""

    # Authentication & Authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_TOKEN = "INVALID_TOKEN"

    # Input Validation
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    INVALID_URL = "INVALID_URL"

    # Tool Execution
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    YOUTUBE_API_ERROR = "YOUTUBE_API_ERROR"
    TRANSCRIPT_NOT_AVAILABLE = "TRANSCRIPT_NOT_AVAILABLE"

    # System Errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: ErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(None, description="Additional error context")
    correlation_id: str | None = Field(None, description="Request correlation ID")


# Custom exception classes
class MCPError(Exception):
    """Base exception for MCP server errors."""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class AuthenticationError(MCPError):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(ErrorCode.UNAUTHORIZED, message)


class InvalidInputError(MCPError):
    """Invalid input provided."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.INVALID_INPUT, message, details)


class ToolExecutionError(MCPError):
    """Tool execution failed."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(ErrorCode.TOOL_EXECUTION_ERROR, message, details)
