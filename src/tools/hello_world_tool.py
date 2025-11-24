# src/tools/hello_world_tool.py
from typing import Any

from src.models.mcp import ToolExecutionContext
from src.tools.base import BaseMCPTool


class HelloWorldTool(BaseMCPTool):
    """
    A simple tool for testing the tool registry.
    It takes no input and returns 'hello world'.
    """

    @property
    def name(self) -> str:
        return "hello_world"

    @property
    def description(self) -> str:
        return "A simple tool that returns the string 'hello world'."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def handler(self, params: dict[str, Any], context: ToolExecutionContext) -> Any:
        context.logger.info("HelloWorldTool handler invoked", input_params=params)
        return "hello world"
