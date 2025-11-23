"""Unit tests for the logging configuration module."""

import logging
from unittest.mock import patch

import pytest
import structlog
from structlog.dev import ConsoleRenderer
from structlog.processors import JSONRenderer

from src.utils.logging import configure_logging, get_logger


@pytest.fixture(autouse=True)
def reset_logging():
    """Fixture to reset logging configuration before and after each test."""
    # Store original state
    original_logging_config = logging.root.manager.loggerDict.copy()
    original_structlog_config = structlog.get_config()

    yield

    # Restore original state
    logging.root.manager.loggerDict = original_logging_config
    logging.root.handlers.clear()
    structlog.configure(
        **original_structlog_config
    )


def test_configure_logging_info_level():
    """Test that logging is configured with JSONRenderer for INFO level."""
    with patch("structlog.configure") as mock_structlog_configure:
        configure_logging(log_level="INFO")

        # Check that the root logger level is set correctly
        assert logging.getLevelName(logging.getLogger().level) == "INFO"

        # Check that structlog was configured
        mock_structlog_configure.assert_called_once()

        # Check that the renderer is JSONRenderer
        args, kwargs = mock_structlog_configure.call_args
        processors = kwargs.get("processors", [])
        assert any(isinstance(p, JSONRenderer) for p in processors)
        assert not any(isinstance(p, ConsoleRenderer) for p in processors)


def test_configure_logging_debug_level():
    """Test that logging is configured with ConsoleRenderer for DEBUG level."""
    with patch("structlog.configure") as mock_structlog_configure:
        configure_logging(log_level="DEBUG")

        # Check that the root logger level is set correctly
        assert logging.getLevelName(logging.getLogger().level) == "DEBUG"

        # Check that structlog was configured
        mock_structlog_configure.assert_called_once()

        # Check that the renderer is ConsoleRenderer
        args, kwargs = mock_structlog_configure.call_args
        processors = kwargs.get("processors", [])
        assert any(isinstance(p, ConsoleRenderer) for p in processors)
        assert not any(isinstance(p, JSONRenderer) for p in processors)


def test_get_logger_returns_logger():
    """Test that get_logger returns a valid logger instance."""
    configure_logging()
    logger = get_logger("test_logger")
    # Check if it's a structlog bound logger (resolved from proxy)
    assert isinstance(logger.bind(), structlog.stdlib.BoundLogger)

