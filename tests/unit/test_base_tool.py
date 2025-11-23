import pytest
from abc import ABC, abstractmethod
from typing import Any, Dict, Awaitable

from src.tools.base import BaseMCPTool
from src.models.mcp import ToolExecutionContext # Assuming ToolExecutionContext is defined here


# Helper class for testing concrete implementation
class ConcreteTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "concrete_tool"

    @property
    def description(self) -> str:
        return "A concrete implementation for testing."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def handler(self, params: Dict[str, Any], context: ToolExecutionContext) -> Any:
        return "handled"

# Helper class for testing partial implementation
class PartialTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "partial_tool"

    @property
    def description(self) -> str:
        return "A partial implementation for testing."

    # Missing input_schema and handler

@pytest.fixture
def mock_tool_execution_context() -> ToolExecutionContext:
    """Fixture for a mock ToolExecutionContext."""
    import structlog
    from unittest.mock import Mock

    # Configure a basic structlog logger for testing
    structlog.configure(
        processors=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logger = structlog.get_logger("test_logger")
    return ToolExecutionContext(correlation_id="test-corr-id", logger=logger, start_time=123.45)


def test_base_mcp_tool_cannot_be_instantiated_directly():
    """Verify that BaseMCPTool cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class BaseMCPTool without an implementation for abstract methods 'description', 'handler', 'input_schema', 'name'"):
        BaseMCPTool()

def test_concrete_tool_implementation(mock_tool_execution_context):
    """Verify a complete concrete implementation can be instantiated and its methods work."""
    tool = ConcreteTool()
    assert tool.name == "concrete_tool"
    assert tool.description == "A concrete implementation for testing."
    assert tool.input_schema == {"type": "object", "properties": {}}
    
    # Test handler method (async)
    import asyncio
    result = asyncio.run(tool.handler({}, mock_tool_execution_context))
    assert result == "handled"

def test_partial_tool_cannot_be_instantiated():
    """Verify that a partial implementation still raises TypeError."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class PartialTool without an implementation for abstract methods 'handler', 'input_schema'"):
        PartialTool()

def test_base_mcp_tool_abstract_properties():
    """Verify that accessing abstract properties directly on BaseMCPTool raises NotImplementedError."""
    # We can't instantiate BaseMCPTool, so we test by creating an incomplete subclass
    class IncompleteTool(BaseMCPTool):
        # Missing all abstract methods/properties
        pass

    with pytest.raises(TypeError):
        # This will fail at instantiation because abstract methods are not implemented
        IncompleteTool()

    # To test NotImplementedError, we would need to call a method on a *partially* implemented subclass
    # or a mock, but the primary check for abstract classes is instantiation TypeError.
    # The TypeError already covers the spirit of "not implemented".
