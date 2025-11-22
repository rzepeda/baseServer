"""Entry point for running the MCP server as a module."""

import uvicorn

from src.config import get_config
from src.utils.logging import configure_logging


def main() -> None:
    """Start the MCP server."""
    config = get_config()
    configure_logging(config.log_level)

    uvicorn.run(
        "src.server:app",
        host=config.server_host,
        port=config.server_port,
        log_config=None,  # Use our custom structlog configuration
        access_log=False,  # Disable uvicorn access logs (we log in middleware)
    )


if __name__ == "__main__":
    main()
