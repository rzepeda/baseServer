"""Pure JSON-RPC handler for MCP protocol (Claude.ai compatible)."""

from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.models.mcp import ToolExecutionContext
from src.registry.tool_registry import ToolRegistry
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request."""

    jsonrpc: str
    id: int | str
    method: str
    params: dict = {}


@router.post("/mcp")
async def jsonrpc_mcp_handler(rpc_request: JSONRPCRequest, request: Request):
    """
    Pure JSON-RPC 2.0 handler for MCP protocol.

    This endpoint provides Claude.ai-compatible responses without SSE wrapping.
    """
    method = rpc_request.method
    params = rpc_request.params
    request_id = rpc_request.id

    logger.info("JSON-RPC request", method=method, id=request_id)

    try:
        # Get tool registry
        registry = ToolRegistry()

        if method == "initialize":
            # MCP initialize handshake
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "experimental": {},
                            "prompts": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                            "tools": {"listChanged": False},
                        },
                        "serverInfo": {
                            "name": "youtube-transcript-server",
                            "version": "1.22.0",
                        },
                    },
                }
            )

        elif method == "tools/list":
            # List available tools
            tools_schema = registry.generate_mcp_schema()
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": [tool.model_dump() for tool in tools_schema]},
                }
            )

        elif method == "tools/call":
            # Call a tool
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if not tool_name:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing 'name' parameter",
                        },
                    },
                    status_code=400,
                )

            # Get the tool
            tool = registry.get_tool(tool_name)
            if not tool:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool '{tool_name}' not found",
                        },
                    },
                    status_code=404,
                )

            # Create execution context
            correlation_id = str(uuid4())
            bound_logger = logger.bind(correlation_id=correlation_id)
            tool_context = ToolExecutionContext(
                correlation_id=correlation_id,
                logger=bound_logger,
                auth_context=getattr(request.state, "auth_context", None),
            )

            # Execute the tool
            bound_logger.info("Executing tool via JSON-RPC", tool_name=tool_name)
            result = await tool.handler(arguments, tool_context)

            # Format result for MCP protocol
            # Convert string result to MCP content format
            if isinstance(result, str):
                content = [{"type": "text", "text": result}]
            elif hasattr(result, "full_text"):
                # YouTubeTranscript model
                content = [{"type": "text", "text": result.full_text}]
            else:
                content = [{"type": "text", "text": str(result)}]

            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": content,
                        "isError": False,
                    },
                }
            )

        else:
            # Unknown method
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"},
                },
                status_code=404,
            )

    except Exception as e:
        logger.error("JSON-RPC handler error", error=str(e), exc_info=True)
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            },
            status_code=500,
        )
