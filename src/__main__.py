"""Entry point for running the MCP and REST API servers as a module."""

import asyncio

import uvicorn

from src.config import get_config
from src.mcp_server import app as mcp_app  # Import the FastAPI app from mcp_server.py
from src.server import app as rest_api_app  # Import the FastAPI app from server.py
from src.utils.logging import configure_logging


def main() -> None:
    """Start the MCP and REST API servers."""
    config = get_config()
    configure_logging(config.log_level)

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
