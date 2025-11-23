from typing import Dict, Optional, List, Any, Callable, Awaitable
from inspect import iscoroutinefunction
from jsonschema import validate, ValidationError

from src.tools.base import BaseMCPTool
from src.models.mcp import MCPToolDefinition # Import MCPToolDefinition


class ToolRegistrationError(Exception):
    """Custom exception for tool registration errors."""
    pass


class ToolRegistry:
    """
    Manages the registration and retrieval of MCP tools.
    Implemented as a singleton to ensure a single, consistent registry throughout the application.
    """
    _instance: Optional['ToolRegistry'] = None
    _registered_tools: Dict[str, BaseMCPTool] = {}

    def __new__(cls) -> 'ToolRegistry':
        if cls._instance is None:
            cls._instance = super(ToolRegistry, cls).__new__(cls)
            # Initialize _registered_tools only once when the first instance is created
            cls._registered_tools = {}
        return cls._instance

    def register_tool(self, tool: BaseMCPTool) -> None:
        """
        Registers an MCP tool with the registry after performing comprehensive validation.

        Args:
            tool: An instance of a class inheriting from BaseMCPTool.

        Raises:
            ToolRegistrationError: If the tool is invalid or a duplicate name is found.
        """
        self._validate_tool_instance(tool)
        self._validate_tool_properties(tool)
        self._validate_duplicate_name(tool)
        self._validate_input_schema(tool)

        self._registered_tools[tool.name] = tool

    def _validate_tool_instance(self, tool: Any) -> None:
        """Checks if the provided object is an instance of BaseMCPTool."""
        if not isinstance(tool, BaseMCPTool):
            raise ToolRegistrationError(f"Provided object is not an instance of BaseMCPTool: {type(tool)}")

    def _validate_tool_properties(self, tool: BaseMCPTool) -> None:
        """Validates that the tool has all required and correctly typed properties."""
        if not tool.name or not isinstance(tool.name, str):
            raise ToolRegistrationError("Tool must have a non-empty string 'name'.")
        if not tool.description or not isinstance(tool.description, str):
            raise ToolRegistrationError(f"Tool '{tool.name}' must have a non-empty string 'description'.")
        if not isinstance(tool.input_schema, dict):
            raise ToolRegistrationError(f"Tool '{tool.name}' must have a 'input_schema' of type dict.")
        if not (callable(tool.handler) and iscoroutinefunction(tool.handler)):
            raise ToolRegistrationError(f"Tool '{tool.name}' must have an async 'handler' method.")

    def _validate_duplicate_name(self, tool: BaseMCPTool) -> None:
        """Checks if a tool with the same name is already registered."""
        if tool.name in self._registered_tools:
            raise ToolRegistrationError(f"Tool with name '{tool.name}' already registered.")

    def _validate_input_schema(self, tool: BaseMCPTool) -> None:
        """Validates the tool's input_schema as a well-formed JSON Schema."""
        try:
            # A very basic validation to check if it's a well-formed JSON schema
            # For now, we provide a dummy instance to satisfy 'required' fields for simple validation.
            # A more robust solution might validate against a meta-schema directly.
            dummy_instance = {}
            if "required" in tool.input_schema and len(tool.input_schema["required"]) > 0:
                for prop in tool.input_schema["required"]:
                    dummy_instance[prop] = "dummy_value" # Provide a dummy value for required fields
            validate(instance=dummy_instance, schema=tool.input_schema)
        except ValidationError as e:
            raise ToolRegistrationError(f"Tool '{tool.name}' has an invalid 'input_schema': {e.message}")
        except Exception as e:
            raise ToolRegistrationError(f"Tool '{tool.name}' has an invalid 'input_schema': {e}")

    def get_tool(self, tool_name: str) -> Optional[BaseMCPTool]:
        """
        Retrieves a registered tool by its name.

        Args:
            tool_name: The name of the tool to retrieve.

        Returns:
            The BaseMCPTool instance if found, otherwise None.
        """
        return self._registered_tools.get(tool_name)

    def get_registered_tool_names(self) -> List[str]:
        """
        Returns a list of names of all currently registered tools.

        Returns:
            A list of strings, where each string is the name of a registered tool.
        """
        return list(self._registered_tools.keys())

    def generate_mcp_schema(self) -> List[MCPToolDefinition]:
        """
        Generates a list of MCPToolDefinition objects for all registered tools.
        This is used to expose the available tools and their schemas to the MCP client.

        Returns:
            A list of MCPToolDefinition objects.
        """
        mcp_schema: List[MCPToolDefinition] = []
        for tool in self._registered_tools.values():
            mcp_schema.append(
                MCPToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    version="1.0" # Assuming default version 1.0 for now
                )
            )
        return mcp_schema

    def _clear(self) -> None:
        """
        Clears all registered tools.
        Primarily for testing purposes to reset the singleton state.
        """
        self._registered_tools.clear()