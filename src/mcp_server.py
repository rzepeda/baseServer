"""
This module defines the MCP Protocol-compliant application using Anthropic's FastMCP SDK.
It is intended to be mounted into a parent ASGI application.
"""

from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from src.config import get_config as _get_config  # Moved to top
from src.models.mcp import ToolExecutionContext
from src.registry.tool_registry import ToolRegistry
from src.utils.context import auth_context_var
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Use singleton tool registry (tools are registered in __main__.py)
tool_registry = ToolRegistry()

# Load configuration to determine SSE mode
_config = _get_config()

# Initialize FastMCP application
_mcp = FastMCP(
    "youtube-transcript-server",
    stateless_http=not _config.use_sse,
)


@_mcp.tool()
async def get_youtube_transcript(url: str) -> str:
    """
    Fetches the transcript for a given YouTube video URL.
    Supports standard (youtube.com), short (youtu.be), and mobile (m.youtube.com) URLs.
    """
    tool_instance = tool_registry.get_tool("get_youtube_transcript")
    if not tool_instance:
        logger.error("youtube_tool_not_found_in_registry")
        return "Error: YouTube transcript tool not found in registry."

    try:
        correlation_id = str(uuid4())
        bound_logger = logger.bind(correlation_id=correlation_id)
        auth_context = auth_context_var.get()
        auth_context_dict = auth_context.model_dump() if auth_context else None

        tool_context = ToolExecutionContext(
            correlation_id=correlation_id, logger=bound_logger, auth_context=auth_context_dict
        )

        result = await tool_instance.handler({"url": url}, tool_context)

        if hasattr(result, "full_text"):
            return str(result.full_text)
        return str(result)

    except Exception as e:
        logger.error(
            "mcp_tool_execution_error",
            tool_name="get_youtube_transcript",
            error=str(e),
            exc_info=True,
        )
        return f"Error executing tool: {type(e).__name__} - {str(e)}"


# Export the proper ASGI app based on configuration
if _config.use_sse:
    logger.info("Exporting MCP SSE ASGI app")
    mcp_app = _mcp.sse_app()
else:
    logger.info("Exporting MCP Streamable HTTP ASGI app")
    mcp_app = _mcp.streamable_http_app()
