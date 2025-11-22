"""Main ASGI application and MCP server implementation."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.config import get_config
from src.handlers.health import health_check
from src.middleware.oauth import oauth_middleware
from src.registry.tool_registry import ToolRegistry
from src.tools.youtube_tool import YouTubeTool
from src.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan (startup and shutdown)."""
    # Startup
    logger.info("Starting MCP server", version="0.1.0")
    config = get_config()
    logger.info(
        "Configuration loaded",
        environment=config.environment,
        log_level=config.log_level,
    )

    # Initialize tool registry
    registry = ToolRegistry()
    registry.register_tool(YouTubeTool())
    app.state.registry = registry
    logger.info("Tool registry initialized", tool_count=len(registry.list_tools()))

    yield

    # Shutdown
    logger.info("Shutting down MCP server")


# Create FastAPI application
app = FastAPI(
    title="YouTube MCP Server",
    description="MCP server for YouTube transcript extraction",
    version="0.1.0",
    lifespan=lifespan,
)

# Add OAuth middleware (applies to all routes except /health)
app.middleware("http")(oauth_middleware)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint for Kubernetes probes."""
    return await health_check(app.state.registry)


@app.post("/tools/invoke")
async def invoke_tool(request: Request) -> JSONResponse:
    """MCP tool invocation endpoint."""
    # TODO: Implement MCP tool invocation handler
    # This will be implemented in the next phase
    return JSONResponse({"status": "not_implemented"}, status_code=501)


@app.get("/tools/list")
async def list_tools(request: Request) -> JSONResponse:
    """List available MCP tools."""
    registry: ToolRegistry = request.app.state.registry
    tools = registry.generate_mcp_schema()
    return JSONResponse({"tools": tools})
