"""Main ASGI application and MCP server implementation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate
from pydantic import BaseModel
from starlette import status
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_config
from src.handlers.health import health_check
from src.handlers.jsonrpc_mcp import router as jsonrpc_router
from src.middleware.oauth import OAuthMiddleware
from src.models.errors import ErrorCode, MCPError
from src.models.mcp import MCPToolDefinition, ToolExecutionContext
from src.registry.tool_registry import ToolRegistrationError, ToolRegistry
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

    # Use singleton tool registry (tools are registered in __main__.py)
    registry = ToolRegistry()
    app.state.registry = registry
    logger.info("Tool registry accessed", tool_count=len(registry.get_registered_tool_names()))

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

# Include JSON-RPC MCP router (Claude.ai compatible endpoint)
app.include_router(jsonrpc_router)
logger.info("JSON-RPC MCP endpoint registered at /mcp")

# Add OAuth middleware (applies to all routes except /health and /mcp for now)
config = get_config()
if config.use_oauth:
    logger.info("OAuth middleware enabled for REST API server.")
    app.add_middleware(OAuthMiddleware, exclude_paths=["/health", "/mcp"])
else:
    logger.warning("OAuth middleware is disabled for REST API server. This is not safe for production.")

# Add CORS middleware to allow requests from specific origins
if config.cors_allowed_origins:
    origins = [origin.strip() for origin in config.cors_allowed_origins.split(",")]
    logger.info("CORS middleware enabled", allowed_origins=origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.warning("CORS middleware is disabled as no origins are configured. This may prevent web-based clients from connecting.")



@app.get("/health")
async def health(request: Request) -> JSONResponse:
    """Health check endpoint for Kubernetes probes."""
    # Use ToolRegistry singleton directly instead of app.state
    # This makes health check work even before lifespan completes
    registry = ToolRegistry()
    return await health_check(registry)


@app.post("/tools/invoke")
async def invoke_tool(request: Request) -> JSONResponse:
    """MCP tool invocation endpoint."""
    registry: ToolRegistry = request.app.state.registry
    correlation_id = str(uuid4())
    bound_logger = logger.bind(correlation_id=correlation_id)

    try:
        request_body = await request.json()
        tool_name = request_body.get("tool_name")
        parameters = request_body.get("parameters", {})

        if not tool_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "tool_name is required", "error_code": "missing_tool_name"},
            )

        tool = registry.get_tool(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": f"Tool '{tool_name}' not found", "error_code": "tool_not_found"},
            )

        # Validate parameters against tool's input schema
        try:
            validate(instance=parameters, schema=tool.input_schema)
        except JSONSchemaValidationError as e:
            bound_logger.warning("Parameter validation failed", tool_name=tool_name, error=str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": f"Invalid parameters: {e.message}",
                    "error_code": "invalid_parameters",
                },
            ) from e

        # Create ToolExecutionContext
        tool_context = ToolExecutionContext(
            correlation_id=correlation_id,
            logger=bound_logger,
            auth_context=getattr(request.state, "auth_context", None),  # Safely access auth_context
        )

        bound_logger.info("Invoking tool", tool_name=tool_name, parameters=parameters)
        result = await tool.handler(parameters, tool_context)
        bound_logger.info("Tool invocation successful", tool_name=tool_name)

        # Serialize Pydantic models to dict for JSON response
        if isinstance(result, BaseModel):
            result = result.model_dump()

        return JSONResponse({"result": result})

    except HTTPException as http_exc:
        bound_logger.warning(
            "HTTP Exception during tool invocation",
            detail=http_exc.detail,
            status_code=http_exc.status_code,
        )
        return JSONResponse(http_exc.detail, status_code=http_exc.status_code)
    except MCPError as mcp_error:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if mcp_error.code == ErrorCode.INVALID_URL:
            status_code = status.HTTP_400_BAD_REQUEST
        elif mcp_error.code == ErrorCode.TRANSCRIPT_NOT_AVAILABLE:
            status_code = status.HTTP_404_NOT_FOUND
        elif (
            mcp_error.code == ErrorCode.SERVICE_UNAVAILABLE
            or mcp_error.code == ErrorCode.YOUTUBE_API_ERROR
        ):
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        bound_logger.warning(
            "MCPError during tool invocation",
            error_code=mcp_error.code,
            message=mcp_error.message,
            status_code=status_code,
        )
        return JSONResponse(
            {"error": mcp_error.message, "error_code": mcp_error.code.value},
            status_code=status_code,
        )
    except ToolRegistrationError as e:
        bound_logger.error("Tool registration error during invocation context", error=str(e))
        return JSONResponse(
            {"error": "Internal server error during tool setup", "error_code": "tool_setup_error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as e:
        bound_logger.error(
            "Unhandled exception during tool invocation", error=str(e), exc_info=True
        )
        return JSONResponse(
            {"error": "Internal server error", "error_code": "unhandled_exception"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@app.get("/tools/list")
async def list_tools(request: Request) -> list[MCPToolDefinition]:
    """List available MCP tools."""
    registry: ToolRegistry = request.app.state.registry
    return registry.generate_mcp_schema()
