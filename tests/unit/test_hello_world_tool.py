import pytest
from typing import Any, Dict

from src.tools.hello_world_tool import HelloWorldTool
from src.models.mcp import ToolExecutionContext


@pytest.mark.asyncio
async def test_hello_world_tool_handler():
    """Test that HelloWorldTool handler returns 'hello world'."""
    # Arrange
    tool = HelloWorldTool()
    
    # Create a mock execution context
    from unittest.mock import Mock
    mock_logger = Mock()
    mock_context = ToolExecutionContext(
        correlation_id="test-corr-id",
        logger=mock_logger,
        auth_context=None,
        start_time=123.45
    )

    # Act
    result = await tool.handler({}, mock_context)

    # Assert
    assert result == "hello world"
    mock_logger.info.assert_called_with("HelloWorldTool handler invoked", input_params={})


def test_hello_world_tool_properties():
    """Test the properties of HelloWorldTool."""
    # Arrange
    tool = HelloWorldTool()

    # Assert
    assert tool.name == "hello_world"
    assert tool.description == "A simple tool that returns the string 'hello world'."
    assert tool.input_schema == {"type": "object", "properties": {}}
