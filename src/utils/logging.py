"""Logging configuration for the application."""

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure logging for the application.
    This should be called once at application startup.
    """
    log_level = log_level.upper()

    # Configure standard library logging for structlog to bridge to
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            (
                structlog.dev.ConsoleRenderer()
                if log_level == "DEBUG"
                else structlog.processors.JSONRenderer()
            ),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure the standard library formatter to use structlog processors
    # This captures logs from the standard logging library and formats them
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=(
            structlog.dev.ConsoleRenderer()
            if log_level == "DEBUG"
            else structlog.processors.JSONRenderer()
        ),
        foreign_pre_chain=[structlog.contextvars.merge_contextvars],
        fmt="%(message)s",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Clear existing handlers
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def get_logger(name: str) -> Any:
    """Get a configured structlog logger."""
    # After configure_logging has been called, structlog.get_logger will return
    # a logger that uses the global configuration.
    return structlog.get_logger(name)
