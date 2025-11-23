"""Main ASGI application and MCP server implementation."""
from uuid import uuid4
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette import status
from pydantic import BaseModel
from jsonschema import validate, ValidationError as JSONSchemaValidationError

from src.config import get_config
from src.handlers.health import health_check
from src.middleware.oauth import oauth_middleware
from src.registry.tool_registry import ToolRegistry, ToolRegistrationError
from src.models.mcp import ToolExecutionContext, MCPToolDefinition
from src.models.errors import MCPError, ErrorCode
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
    try:
        registry.register_tool(YouTubeTool())
        logger.info("Registered YouTubeTool successfully.")
    except ToolRegistrationError as e:
        logger.error("Failed to register YouTubeTool", error=str(e))
    
    app.state.registry = registry
    logger.info("Tool registry initialized", tool_count=len(registry.get_registered_tool_names()))

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
                detail={"error": "tool_name is required", "error_code": "missing_tool_name"}
            )

        tool = registry.get_tool(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": f"Tool '{tool_name}' not found", "error_code": "tool_not_found"}
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
                    "error_code": "invalid_parameters"
                }
            )

        # Create ToolExecutionContext
        tool_context = ToolExecutionContext(
            correlation_id=correlation_id,
            logger=bound_logger,
            auth_context=getattr(request.state, "auth_context", None) # Safely access auth_context
        )

        bound_logger.info("Invoking tool", tool_name=tool_name, parameters=parameters)
        result = await tool.handler(parameters, tool_context)
        bound_logger.info("Tool invocation successful", tool_name=tool_name)

        # Serialize Pydantic models to dict for JSON response
        if isinstance(result, BaseModel):
            result = result.model_dump()

        return JSONResponse({"result": result})

    except HTTPException as http_exc:
        bound_logger.warning("HTTP Exception during tool invocation", detail=http_exc.detail, status_code=http_exc.status_code)
        return JSONResponse(http_exc.detail, status_code=http_exc.status_code)
    except MCPError as mcp_error:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if mcp_error.code == ErrorCode.INVALID_URL:
            status_code = status.HTTP_400_BAD_REQUEST
        elif mcp_error.code == ErrorCode.TRANSCRIPT_NOT_AVAILABLE or mcp_error.code == ErrorCode.YOUTUBE_API_ERROR:
            status_code = status.HTTP_404_NOT_FOUND # Mapping both to 404 for clarity when content not found
        elif mcp_error.code == ErrorCode.SERVICE_UNAVAILABLE or mcp_error.code == ErrorCode.YOUTUBE_API_ERROR:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE # For actual service unavailable/network errors

        bound_logger.warning("MCPError during tool invocation", error_code=mcp_error.code, message=mcp_error.message, status_code=status_code)
        return JSONResponse({"error": mcp_error.message, "error_code": mcp_error.code.value}, status_code=status_code)
    except ToolRegistrationError as e:
        bound_logger.error("Tool registration error during invocation context", error=str(e))
        return JSONResponse({"error": "Internal server error during tool setup", "error_code": "tool_setup_error"},
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        bound_logger.error("Unhandled exception during tool invocation", error=str(e), exc_info=True)
        return JSONResponse({"error": "Internal server error", "error_code": "unhandled_exception"},
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.get("/tools/list")
async def list_tools(request: Request) -> List[MCPToolDefinition]:
    """List available MCP tools."""
    registry: ToolRegistry = request.app.state.registry
    return registry.generate_mcp_schema()