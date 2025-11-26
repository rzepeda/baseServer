"""Minimal MCP server for debugging connection issues.

This is a proof-of-concept implementation following the official MCP SDK pattern.
It provides a single static tool with no parameters or complex logic to isolate
whether Cloudflare tunnel + Claude.ai integration works with a baseline implementation.
"""

from datetime import UTC, datetime

from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Initialize minimal FastMCP server
# Don't use stateless mode - Claude.ai needs SSE endpoints
mcp = FastMCP("minimal-mcp-server")


@mcp.tool()
async def hello() -> str:
    """
    Returns a simple greeting message.

    This is a minimal test tool with no parameters or complex logic.
    Used for debugging MCP server connectivity with Claude.ai via Cloudflare tunnel.

    Returns:
        A static greeting message
    """
    logger.info("hello_tool_invoked")
    return "Hello from minimal MCP server!"


@mcp.custom_route("/health", methods=["GET"])  # type: ignore[misc]
async def health_endpoint(request: Request) -> JSONResponse:
    """Health check endpoint for tunnel validation."""
    logger.info("health_check_requested")
    response_data = {
        "status": "healthy",
        "server": "minimal-mcp-server",
        "version": "0.1.0",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return JSONResponse(content=response_data)


# Export the ASGI application from FastMCP
# Strategy: Create a wrapper app that handles health independently,
# then passes everything else to the MCP SSE app
from starlette.applications import Starlette
from starlette.routing import Mount, Route


# Independent health handler - NOT part of MCP routing
async def health_handler(request: Request) -> JSONResponse:
    """Health check endpoint for tunnel validation - completely independent."""
    logger.info("health_check_requested")
    response_data = {
        "status": "healthy",
        "server": "minimal-mcp-server",
        "version": "0.1.0",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return JSONResponse(content=response_data)


# Get the SSE app from FastMCP - this handles MCP protocol
sse_app_instance = mcp.sse_app()

# Create main app with routes - health route BEFORE MCP mount
# This ensures /health is handled first, before MCP routing
app = Starlette(
    routes=[
        Route("/health", health_handler, methods=["GET"]),  # Priority route
        Mount("/", sse_app_instance),  # MCP at root (includes /sse endpoint)
    ]
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("minimal_mcp_server_initialized")
