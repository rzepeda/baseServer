"""Entry point for running the unified MCP and REST API server."""

import uvicorn

from src.config import get_config
from src.registry.tool_registry import ToolRegistry, register_all_tools
from src.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


def main() -> None:
    """Entry point for running the unified server."""
    # CRITICAL: Register all tools BEFORE the server app is imported and configured
    register_all_tools()
    logger.info("Tools registered.", tool_count=len(ToolRegistry().get_registered_tool_names()))

    # Get config and configure logging
    config = get_config()
    configure_logging(config.log_level)

    logger.info(
        "Starting unified server on port %s",
        config.mcp_port,
    )

    # Run the single, unified server from src.server
    uvicorn.run(
        "src.server:app",
        host=config.server_host,
        port=config.mcp_port,
        log_config=None,  # Use our custom structlog configuration
        access_log=False,
    )


if __name__ == "__main__":
    main()
