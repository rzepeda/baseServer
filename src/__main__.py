"""Entry point for running the MCP and REST API servers as a module."""

import asyncio

import uvicorn

from src.config import get_config
from src.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


def main() -> None:
    """Start the MCP server (minimal or full) and optionally REST API server."""
    config = get_config()
    configure_logging(config.log_level)

    if config.use_minimal_server:
        # Run only the minimal MCP server on port 8080
        logger.info("starting_minimal_mcp_server_mode", port=config.mcp_port)
        from src.minimal_mcp_server import app as minimal_mcp_app

        uvicorn.run(
            minimal_mcp_app,
            host=config.server_host,
            port=config.mcp_port,
            log_config=None,  # Use our custom structlog configuration
            access_log=False,  # Disable uvicorn access logs
        )
    else:
        # Run full dual-server mode (MCP + REST API)
        logger.info(
            "starting_dual_server_mode",
            mcp_port=config.mcp_port,
            rest_api_port=config.rest_api_port,
        )
        from src.mcp_server import app as mcp_app
        from src.server import app as rest_api_app

        # Uvicorn configurations for both servers
        mcp_server_config = uvicorn.Config(
            mcp_app,
            host=config.server_host,
            port=config.mcp_port,
            log_config=None,  # Use our custom structlog configuration
            access_log=False,  # Disable uvicorn access logs (we log in middleware)
        )

        rest_api_server_config = uvicorn.Config(
            rest_api_app,
            host=config.server_host,
            port=config.rest_api_port,
            log_config=None,  # Use our custom structlog configuration
            access_log=False,  # Disable uvicorn access logs (we log in middleware)
        )

        # Create server instances
        mcp_server = uvicorn.Server(mcp_server_config)
        rest_api_server = uvicorn.Server(rest_api_server_config)

        # Run both servers concurrently
        async def run_servers() -> None:
            await asyncio.gather(mcp_server.serve(), rest_api_server.serve())

        asyncio.run(run_servers())


if __name__ == "__main__":
    main()
