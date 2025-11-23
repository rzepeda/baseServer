# How to Create and Register New MCP Tools

This document outlines the process for developing and integrating new tools into the MCP Server's extensible tool registry. Following these guidelines ensures that your tools are correctly recognized, validated, and callable by the server.

## 1. Understand the `BaseMCPTool` Interface

All new tools must inherit from the `BaseMCPTool` abstract base class, defined in `src/tools/base.py`. This class enforces a standard structure for all tools by requiring the implementation of specific properties and an asynchronous handler method.

### Required Components of a `BaseMCPTool`:

-   **`name` (property: `str`)**: A unique, descriptive string that identifies your tool within the registry. This name will be used by clients to invoke your tool.
-   **`description` (property: `str`)**: A brief, human-readable explanation of what your tool does. This description is exposed in the MCP schema and helps users understand the tool's purpose.
-   **`input_schema` (property: `Dict[str, Any]`)**: A JSON Schema object that defines the expected input parameters for your tool's `handler` method. This schema is crucial for input validation and for generating the tool's manifest in the MCP protocol. It ensures that calls to your tool provide the necessary data in the correct format.
-   **`handler` (async method: `(self, params: Dict[str, Any], context: ToolExecutionContext) -> Any`)**: The asynchronous function that contains the core logic of your tool.
    -   `params`: A dictionary containing the input parameters, validated against your `input_schema`.
    -   `context`: An instance of `ToolExecutionContext`, providing runtime context such as `correlation_id` (for logging and tracing) and a bound `logger`.
    -   The handler should return a JSON-serializable result.

### Example `BaseMCPTool` Implementation Structure:

```python
# src/tools/my_new_tool.py
from typing import Any, Dict
from src.tools.base import BaseMCPTool
from src.models.mcp import ToolExecutionContext

class MyNewTool(BaseMCPTool):
    @property
    def name(self) -> str:
        return "my_new_tool"

    @property
    def description(self) -> str:
        return "A sample tool that echoes back the input it receives."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "A message to echo back."
                }
            },
            "required": ["message"]
        }

    async def handler(self, params: Dict[str, Any], context: ToolExecutionContext) -> Any:
        context.logger.info("MyNewTool handler invoked", input_params=params)
        message = params.get("message", "No message provided.")
        return {"echoed_message": f"You said: {message}"}
```

## 2. Register Your Tool

Once your tool is implemented, it must be registered with the `ToolRegistry` so the MCP server can discover and expose it. The `ToolRegistry` is a singleton, ensuring that all parts of the application access the same instance.

Tools are typically registered during the server's `lifespan` startup event, usually in `src/server.py`.

### Registration Steps:

1.  **Import your tool**: Add an import statement for your new tool class in `src/server.py`.
2.  **Get the `ToolRegistry` instance**: Retrieve the singleton instance of the `ToolRegistry`.
3.  **Instantiate and Register**: Create an instance of your tool and pass it to the `registry.register_tool()` method.

### Example Registration in `src/server.py`:

```python
# src/server.py (excerpt)
# ... other imports ...
from src.registry.tool_registry import ToolRegistry
from src.tools.my_new_tool import MyNewTool # Import your new tool

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ... startup logic ...
    registry = ToolRegistry() # Get the singleton instance

    # Register your custom tool
    try:
        registry.register_tool(MyNewTool())
        logger.info("Registered MyNewTool successfully.")
    except ToolRegistrationError as e:
        logger.error("Failed to register MyNewTool", error=str(e))

    # ... yield and shutdown logic ...
```

## 3. Tool Validation

The `ToolRegistry` performs several validations during registration to ensure tool integrity:

-   **`BaseMCPTool` inheritance**: Ensures the tool adheres to the basic interface.
-   **Required properties**: `name`, `description`, `input_schema`, and `handler` must be implemented and non-empty/valid.
-   **Unique name**: Prevents duplicate tool names.
-   **Valid JSON Schema**: `input_schema` is validated against the JSON Schema specification.
-   **Asynchronous handler**: The `handler` method must be an `async` function.

If any validation fails, a `ToolRegistrationError` is raised, preventing the invalid tool from being registered.

## 4. Testing Your New Tool

Thoroughly test your tool to ensure it functions as expected:

-   **Unit Tests**: Create a dedicated test file (e.g., `tests/unit/test_my_new_tool.py`) for your tool.
    -   Test the `name`, `description`, and `input_schema` properties.
    -   Test the `handler` method with valid and invalid `params` (if your handler has internal validation).
    -   Mock any external dependencies your tool's handler might have.
-   **Integration Tests**: If your tool interacts with other services, consider integration tests to verify end-to-end functionality.
-   **Manual Testing**: After integrating into `src/server.py`, you can perform manual tests using the `/tools/list` endpoint to see your tool's manifest and the `/tools/invoke` endpoint to call its handler.

By following these steps, you can effectively extend the MCP Server with new capabilities.
