"""MCP Protocol-compliant server using Anthropic's MCP SDK."""

from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.models.mcp import ToolExecutionContext
from src.registry.tool_registry import ToolRegistry
from src.utils.context import auth_context_var
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Use singleton tool registry (tools are registered in __main__.py)
tool_registry = ToolRegistry()

# Initialize FastMCP server
# Use stateless HTTP mode for compatibility with Cloudflare tunnel
# Cloudflare's free tunnel doesn't support SSE streaming properly
mcp = FastMCP(
    "youtube-transcript-server",
    stateless_http=True,  # Allow stateless HTTP requests (no SSE required)
)


@mcp.tool()
async def get_youtube_transcript(url: str) -> str:
    """
    Fetches the transcript for a given YouTube video URL.

    Supports standard (youtube.com), short (youtu.be), and mobile (m.youtube.com) URLs.

    Args:
        url: The full YouTube video URL

    Returns:
        The full transcript text of the video
    """
    # Get the YouTubeTool instance from registry
    tool_instance = tool_registry.get_tool("get_youtube_transcript")
    if not tool_instance:
        logger.error("youtube_tool_not_found_in_registry")
        return "Error: YouTube transcript tool not found in registry."

    try:
        # Create execution context with correlation ID
        correlation_id = str(uuid4())
        bound_logger = logger.bind(correlation_id=correlation_id)

        # Get auth_context from context var
        auth_context = auth_context_var.get()

        auth_context_dict = auth_context.to_dict() if auth_context else None
        tool_context = ToolExecutionContext(
            correlation_id=correlation_id, logger=bound_logger, auth_context=auth_context_dict
        )

        # Execute the tool handler
        result = await tool_instance.handler({"url": url}, tool_context)

        # Extract full_text from YouTubeTranscript result
        if hasattr(result, "full_text"):
            return str(result.full_text)
        else:
            return str(result)

    except Exception as e:
        logger.error(
            "mcp_tool_execution_error",
            tool_name="get_youtube_transcript",
            error=str(e),
            exc_info=True,
        )
        return f"Error executing tool: {type(e).__name__} - {str(e)}"


# Add custom health endpoint using FastMCP's custom_route
@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Request) -> JSONResponse:
    """Health check endpoint for MCP server."""
    from datetime import UTC, datetime

    response_data = {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.now(UTC).isoformat(),
        "tools_loaded": len(tool_registry.get_registered_tool_names()),
        "registered_tools": tool_registry.get_registered_tool_names(),
    }

    return JSONResponse(content=response_data)


from src.middleware.oauth import OAuthMiddleware  # noqa: E402

# Export the ASGI application from FastMCP
# In stateless mode, use streamable_http_app (works with Cloudflare tunnel)
# MCP messages endpoint will be at /messages/
# Apply OAuthMiddleware to protect endpoints, excluding /health
app = OAuthMiddleware(mcp.streamable_http_app(), exclude_paths=["/health"])
