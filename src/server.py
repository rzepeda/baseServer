"""
Main Unified ASGI Server.

This server runs on a single port and serves both the REST API endpoints
and the MCP protocol application, which is mounted at the /mcp path.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate
from pydantic import BaseModel
from starlette import status

from src.config import get_config
from src.handlers.health import health_check
from src.handlers.oauth_discovery import router as oauth_router  # Import the new router
from src.mcp_server import mcp_app
from src.middleware.oauth import OAuthMiddleware
from src.models.mcp import MCPToolDefinition, ToolExecutionContext
from src.registry.tool_registry import ToolRegistry
from src.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan (startup and shutdown)."""
    logger.info("Starting Unified Server", version="0.1.0")
    config = get_config()
    logger.info(
        "Configuration loaded",
        environment=config.environment,
        log_level=config.log_level,
        use_sse=config.use_sse,
    )

    registry = ToolRegistry()
    app.state.registry = registry
    logger.info("Tool registry accessed", tool_count=len(registry.get_registered_tool_names()))
    yield
    logger.info("Shutting down Unified Server")


# Create the main FastAPI application
app = FastAPI(
    title="Unified MCP and REST API Server",
    description="Serves both the MCP protocol endpoint and supporting REST API endpoints.",
    version="0.1.0",
    lifespan=lifespan,
)

# Include the new OAuth discovery router
app.include_router(oauth_router)
logger.info("Mounted OAuth discovery endpoint at /.well-known/oauth-authorization-server")

# Mount the specialized MCP application at the /mcp path
app.mount("/mcp", mcp_app)
logger.info("Mounted MCP application at /mcp")

# Add unified middleware for the entire application
config = get_config()
if config.use_oauth:
    logger.info("OAuth middleware enabled for entire application.")
    app.add_middleware(
        OAuthMiddleware,
        exclude_paths=[
            "/health",
            "/.well-known/oauth-authorization-server",
            "/.well-known/oauth-protected-resource",
            "/register",
        ],
    )
else:
    logger.warning("OAuth middleware is disabled. This is not safe for production.")

if config.cors_allowed_origins:
    origins = [origin.strip() for origin in config.cors_allowed_origins.split(",")]
    logger.info("CORS middleware enabled for entire application", allowed_origins=origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Define REST API endpoints
@app.get("/health")
async def health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    registry = ToolRegistry()
    return await health_check(registry)


@app.post("/register")
async def register_client() -> JSONResponse:
    """
    MCP client registration endpoint.

    In this implementation, we assume clients are pre-configured.
    This endpoint exists for compatibility with clients that expect it.
    """
    logger.info("Client registration endpoint called. Responding with success.")
    # For pre-configured clients, we just need to acknowledge the request.
    return JSONResponse({"status": "registration_acknowledged"}, status_code=200)


@app.get("/tools/list")
async def list_tools(request: Request) -> list[MCPToolDefinition]:
    """List available MCP tools."""
    registry: ToolRegistry = request.app.state.registry
    return registry.generate_mcp_schema()


@app.post("/tools/invoke")
async def invoke_tool(request: Request) -> JSONResponse:
    """REST endpoint to invoke a tool directly."""
    registry: ToolRegistry = request.app.state.registry
    correlation_id = str(uuid4())
    bound_logger = logger.bind(correlation_id=correlation_id)

    try:
        request_body = await request.json()
        tool_name = request_body.get("tool_name")
        parameters = request_body.get("parameters", {})

        if not tool_name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "tool_name is required")

        tool = registry.get_tool(tool_name)
        if not tool:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tool '{tool_name}' not found")

        try:
            validate(instance=parameters, schema=tool.input_schema)
        except JSONSchemaValidationError as e:
            return JSONResponse(
                {"error_code": "invalid_parameters", "error": f"Invalid parameters: {e.message}"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        tool_context = ToolExecutionContext(
            correlation_id=correlation_id,
            logger=bound_logger,
            auth_context=getattr(request.state, "auth_context", None),
        )

        result = await tool.handler(parameters, tool_context)
        if isinstance(result, BaseModel):
            result = result.model_dump()

        return JSONResponse({"result": result})
    except HTTPException:
        raise
    except Exception as e:
        bound_logger.error("Unhandled exception in invoke_tool", error=str(e), exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal Server Error")
