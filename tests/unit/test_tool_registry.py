from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.models.mcp import ToolExecutionContext  # Assuming ToolExecutionContext is defined here
from src.registry.tool_registry import ToolRegistrationError, ToolRegistry
from src.tools.base import BaseMCPTool


class MockTool(BaseMCPTool):
    def __init__(self, name: str, description: str, input_schema: dict, handler: AsyncMock):
        self._name = name
        self._description = description
        self._input_schema = input_schema
        self._handler = handler

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def input_schema(self) -> dict:
        return self._input_schema

    async def handler(self, params: dict, context: ToolExecutionContext) -> Any:
        return await self._handler(params, context)


@pytest.fixture(autouse=True)
def clear_tool_registry():
    """Fixture to clear the ToolRegistry before each test."""
    registry = ToolRegistry()
    registry._clear()
    yield
    registry._clear()


@pytest.fixture
def mock_tool_execution_context() -> ToolExecutionContext:
    """Fixture for a mock ToolExecutionContext."""
    import structlog

    # Configure a basic structlog logger for testing
    structlog.configure(
        processors=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logger = structlog.get_logger("test_logger")
    return ToolExecutionContext(correlation_id="test-corr-id", logger=logger)


@pytest.fixture
def valid_mock_tool_factory(mock_tool_execution_context):
    """Factory fixture for creating valid mock tools."""

    def _factory(name: str):
        mock_handler = AsyncMock(return_value=f"hello from {name}")
        return MockTool(
            name=name,
            description=f"Description for {name}",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            handler=mock_handler,
        )

    return _factory


def test_tool_registry_is_singleton():
    """Verify that ToolRegistry always returns the same instance."""
    registry1 = ToolRegistry()
    registry2 = ToolRegistry()
    assert registry1 is registry2


def test_register_tool_success(valid_mock_tool_factory):
    """Test successful registration of a valid tool."""
    registry = ToolRegistry()
    tool = valid_mock_tool_factory("test_tool")
    registry.register_tool(tool)
    assert registry.get_tool("test_tool") is tool
    assert "test_tool" in registry.get_registered_tool_names()


def test_register_tool_duplicate_name_fails(valid_mock_tool_factory):
    """Test that registering a tool with a duplicate name raises an error."""
    registry = ToolRegistry()
    tool1 = valid_mock_tool_factory("duplicate_tool")
    registry.register_tool(tool1)

    tool2 = valid_mock_tool_factory("duplicate_tool")
    with pytest.raises(
        ToolRegistrationError, match="Tool with name 'duplicate_tool' already registered."
    ):
        registry.register_tool(tool2)


def test_register_tool_missing_name_fails():
    """Test that registering a tool with a missing name raises an error."""
    registry = ToolRegistry()
    tool = MockTool(
        name="",  # Missing name
        description="Description",
        input_schema={"type": "object"},
        handler=AsyncMock(),
    )
    with pytest.raises(ToolRegistrationError, match="Tool must have a non-empty string 'name'."):
        registry.register_tool(tool)


def test_register_tool_missing_description_fails():
    """Test that registering a tool with a missing description raises an error."""
    registry = ToolRegistry()
    tool = MockTool(
        name="test_tool_no_desc",
        description="",  # Missing description
        input_schema={"type": "object"},
        handler=AsyncMock(),
    )
    with pytest.raises(
        ToolRegistrationError,
        match="Tool 'test_tool_no_desc' must have a non-empty string 'description'.",
    ):
        registry.register_tool(tool)


def test_register_tool_invalid_input_schema_fails():
    """Test that registering a tool with an invalid input_schema raises an error."""
    registry = ToolRegistry()
    tool = MockTool(
        name="test_tool_invalid_schema",
        description="Description",
        input_schema={"type": "invalid_type"},  # Invalid JSON schema
        handler=AsyncMock(),
    )
    with pytest.raises(
        ToolRegistrationError, match="Tool 'test_tool_invalid_schema' has an invalid 'input_schema'"
    ):
        registry.register_tool(tool)


def test_register_tool_non_dict_input_schema_fails():
    """Test that registering a tool with a non-dict input_schema raises an error."""
    registry = ToolRegistry()
    tool = MockTool(
        name="test_tool_non_dict_schema",
        description="Description",
        input_schema="not a dict",  # Not a dictionary
        handler=AsyncMock(),
    )
    with pytest.raises(
        ToolRegistrationError,
        match="Tool 'test_tool_non_dict_schema' must have a 'input_schema' of type dict.",
    ):
        registry.register_tool(tool)


def test_register_tool_non_async_handler_fails():
    """Test that registering a tool with a non-async handler raises an error."""
    registry = ToolRegistry()

    class NonAsyncHandlerTool(BaseMCPTool):
        @property
        def name(self) -> str:
            return "non_async_tool"

        @property
        def description(self) -> str:
            return "Tool with a non-async handler"

        @property
        def input_schema(self) -> dict:
            return {"type": "object"}

        def handler(self, params: dict, context: ToolExecutionContext) -> Any:  # type: ignore
            return "sync result"

    tool = NonAsyncHandlerTool()
    with pytest.raises(
        ToolRegistrationError, match="Tool 'non_async_tool' must have an async 'handler' method."
    ):
        registry.register_tool(tool)


def test_get_tool_existing(valid_mock_tool_factory):
    """Test retrieving an existing tool."""
    registry = ToolRegistry()
    tool = valid_mock_tool_factory("existing_tool")
    registry.register_tool(tool)
    retrieved_tool = registry.get_tool("existing_tool")
    assert retrieved_tool is tool


def test_get_tool_non_existing():
    """Test retrieving a non-existing tool returns None."""
    registry = ToolRegistry()
    retrieved_tool = registry.get_tool("non_existing_tool")
    assert retrieved_tool is None


def test_get_registered_tool_names(valid_mock_tool_factory):
    """Test getting a list of registered tool names."""
    registry = ToolRegistry()
    tool1 = valid_mock_tool_factory("tool1")
    tool2 = valid_mock_tool_factory("tool2")
    registry.register_tool(tool1)
    registry.register_tool(tool2)
    names = registry.get_registered_tool_names()
    assert sorted(names) == ["tool1", "tool2"]


def test_get_registered_tool_names_empty():
    """Test getting registered tool names from an empty registry."""
    registry = ToolRegistry()
    names = registry.get_registered_tool_names()
    assert names == []


def test_register_non_base_mcp_tool_fails():
    """Test that registering an object not inheriting from BaseMCPTool raises an error."""
    registry = ToolRegistry()

    class NonMCPTool:
        name = "invalid"
        description = "invalid"
        input_schema = {"type": "object"}

        async def handler(self, params: dict, context: ToolExecutionContext) -> Any:
            return "nope"

    tool = NonMCPTool()
    with pytest.raises(
        ToolRegistrationError, match="Provided object is not an instance of BaseMCPTool"
    ):
        registry.register_tool(tool)
