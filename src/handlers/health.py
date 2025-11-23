"""Health check endpoint handler."""

from datetime import UTC, datetime

from fastapi.responses import JSONResponse

from src.models.mcp import HealthCheckResponse
from src.registry.tool_registry import ToolRegistry


async def health_check(registry: ToolRegistry) -> JSONResponse:
    """
    Handles the health check request.
    Returns a JSON response with the server's health status.
    """
    response_model = HealthCheckResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now(UTC),
        tools_loaded=len(registry.get_registered_tool_names()),
        registered_tools=registry.get_registered_tool_names(),
    )

    return JSONResponse(content=response_model.model_dump(mode="json"))
