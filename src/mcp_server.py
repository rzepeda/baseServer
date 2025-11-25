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

# Load configuration to determine SSE mode
from src.config import get_config as _get_config  # noqa: E402

_config = _get_config()

# Initialize FastMCP server
# Use stateless HTTP mode when USE_SSE=False (required for Claude.ai integration)
# Use SSE mode when USE_SSE=True (for local SSE-capable MCP clients)
mcp = FastMCP(
    "youtube-transcript-server",
    stateless_http=not _config.use_sse,  # Stateless HTTP when SSE is disabled
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
    logger.info("Health check endpoint called.")
    from datetime import UTC, datetime

    response_data = {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": datetime.now(UTC).isoformat(),
        "tools_loaded": len(tool_registry.get_registered_tool_names()),
        "registered_tools": tool_registry.get_registered_tool_names(),
    }

    return JSONResponse(content=response_data)


from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from src.config import get_config  # noqa: E402
from src.middleware.oauth import OAuthMiddleware  # noqa: E402

# Export the ASGI application from FastMCP
# Claude.ai requires SSE transport with /sse and /messages/ endpoints
config = get_config()

# Select the appropriate app based on SSE configuration
if config.use_sse:
    logger.info("SSE mode enabled for MCP server (required for Claude.ai).")
    base_app = mcp.sse_app()  # Call the method to get the ASGI app (returns Starlette app)
else:
    logger.info("Stateless HTTP mode enabled for MCP server (SSE disabled).")
    base_app = mcp.streamable_http_app()

# Apply CORS middleware for Claude.ai using Starlette's built-in CORS
if config.cors_allowed_origins:
    from starlette.middleware.cors import CORSMiddleware as StarletteCORS

    origins = [origin.strip() for origin in config.cors_allowed_origins.split(",")]
    logger.info("CORS middleware enabled for MCP server", allowed_origins=origins)

    # Wrap the Starlette app with CORS middleware
    base_app.add_middleware(
        StarletteCORS,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

# Apply OAuth middleware if enabled
if config.use_oauth:
    logger.info("OAuth middleware enabled for MCP server.")
    app = OAuthMiddleware(base_app, exclude_paths=["/health"])
else:
    logger.warning("OAuth middleware is disabled for MCP server. This is not safe for production.")
    app = base_app
