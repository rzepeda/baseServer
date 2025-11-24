"""Entry point for running the MCP and REST API servers as a module."""

import asyncio

import uvicorn

from src.config import get_config
from src.registry.tool_registry import ToolRegistry
from src.tools.youtube_tool import YouTubeTool
from src.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)

# CRITICAL: Initialize tool registry and register tools BEFORE importing server apps
# This ensures a single registration point, avoiding duplicate registration errors
_registry = ToolRegistry()
_registry.register_tool(YouTubeTool())
logger.info("youtube_tool_registered_in_main", tool_count=len(_registry.get_registered_tool_names()))

# Now import server apps - they will use the already-populated singleton registry
from src.mcp_server import app as mcp_app
from src.server import app as rest_api_app


async def run_mcp_server(config) -> None:
    """Run the MCP Protocol Server on port 8080."""
    mcp_config = uvicorn.Config(
        mcp_app,
        host=config.server_host,
        port=config.mcp_port,
        log_config=None,
        access_log=False,
    )
    mcp_server = uvicorn.Server(mcp_config)
    await mcp_server.serve()


async def run_rest_api_server(config) -> None:
    """Run the REST API Server on port 8081."""
    rest_api_config = uvicorn.Config(
        rest_api_app,
        host=config.server_host,
        port=config.rest_api_port,
        log_config=None,
        access_log=False,
    )
    rest_api_server = uvicorn.Server(rest_api_config)
    await rest_api_server.serve()


async def run_both_servers() -> None:
    """Run both MCP and REST API servers concurrently."""
    config = get_config()
    configure_logging(config.log_level)

    logger.info(
        "Starting dual-server architecture",
        mcp_port=config.mcp_port,
        rest_api_port=config.rest_api_port,
    )

    # Run both servers concurrently
    await asyncio.gather(
        run_mcp_server(config),
        run_rest_api_server(config),
    )


def main() -> None:
    """Entry point for running both servers."""
    asyncio.run(run_both_servers())


if __name__ == "__main__":
    main()
