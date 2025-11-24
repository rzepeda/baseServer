from abc import ABC, abstractmethod
from typing import Any

from src.models.mcp import ToolExecutionContext


class BaseMCPTool(ABC):
    """
    Abstract Base Class for all MCP Tools.

    All tools intended for use with the ToolRegistry must inherit from this class
    and implement its abstract methods and properties.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the tool."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """A brief description of what the tool does."""
        raise NotImplementedError

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """
        The JSON schema defining the expected input parameters for the tool's handler.
        This schema is used for validation and MCP manifest generation.
        """
        raise NotImplementedError

    @abstractmethod
    async def handler(self, params: dict[str, Any], context: ToolExecutionContext) -> Any:
        """
        The asynchronous handler function that executes the tool's logic.

        Args:
            params: A dictionary of parameters validated against `input_schema`.
            context: An instance of `ToolExecutionContext` providing runtime context.

        Returns:
            The result of the tool's execution. Can be any JSON-serializable type.
        """
        raise NotImplementedError
