# Components

Based on the **plugin-based modular monolith** architecture, repository structure (monorepo), and tech stack (Python 3.12, Uvicorn, MCP SDK), here are the major logical components:

## MCP Server Component

**Responsibility:** Core ASGI application handling HTTP requests, MCP protocol communication, request routing, and server lifecycle management.

**Key Interfaces:**
- `POST /tools/invoke` - MCP tool invocation endpoint (requires OAuth)
- `GET /health` - Health check endpoint (no auth required)
- `startup_event()` - Initialize tool registry, load configuration
- `shutdown_event()` - Graceful cleanup

**Dependencies:** ToolRegistry, OAuthMiddleware, LoggingUtility, MCP SDK

**Technology Stack:** Uvicorn, MCP Python SDK, structlog

**Module Location:** `src/server.py`

## OAuth Middleware Component

**Responsibility:** Intercept all incoming requests (except `/health`), validate OAuth 2.0 bearer tokens, attach AuthContext to requests, reject unauthorized access.

**Key Interfaces:**
- `async def oauth_middleware(request, call_next)` - ASGI middleware function
- `async def validate_token(token)` - Token validation logic
- `get_token_from_header(headers)` - Extract bearer token

**Dependencies:** authlib, httpx, LoggingUtility

**Technology Stack:** authlib, httpx, Pydantic

**Module Location:** `src/middleware/oauth.py`

## Tool Registry Component

**Responsibility:** Central registry managing all MCP tools, validating tool definitions, providing tool lookup by name, generating MCP schema for clients.

**Key Interfaces:**
- `register_tool(tool)` - Register new tool at startup
- `get_tool(name)` - Retrieve tool by name
- `list_tools()` - Get all registered tools
- `generate_mcp_schema()` - Generate MCP tools schema
- `async def invoke_tool(...)` - Execute tool handler

**Dependencies:** BaseMCPTool, ErrorHandler, LoggingUtility

**Technology Stack:** Python, jsonschema

**Module Location:** `src/registry/tool_registry.py`

## Base Tool Interface Component

**Responsibility:** Abstract base class defining contract all MCP tools must implement.

**Key Interfaces:**
- `@abstractmethod def get_name()` - Tool identifier
- `@abstractmethod def get_description()` - Tool description
- `@abstractmethod def get_input_schema()` - JSON Schema for parameters
- `@abstractmethod async def execute(...)` - Tool execution logic

**Dependencies:** jsonschema, Pydantic models

**Technology Stack:** Python ABC, jsonschema

**Module Location:** `src/tools/base.py`

## YouTube Tool Component

**Responsibility:** Implement YouTube transcript extraction, URL parsing and validation, error handling for YouTube-specific scenarios.

**Key Interfaces:**
- Implements `BaseMCPTool` interface
- `async def execute(params, context)` - Fetch and return transcript
- `parse_url(url)` - Extract video ID from URL
- `async def fetch_transcript(video_id)` - Call youtube-transcript-api

**Dependencies:** BaseMCPTool, youtube-transcript-api, YouTubeURL model, ErrorHandler

**Technology Stack:** youtube-transcript-api, Pydantic

**Module Location:** `src/tools/youtube_tool.py`

## Error Handler Component

**Responsibility:** Global exception handling, convert Python exceptions to standardized ErrorDetail models, map exception types to HTTP status codes.

**Key Interfaces:**
- `handle_exception(exc, correlation_id)` - Convert exception to ErrorDetail
- `get_http_status(error_code)` - Map error codes to HTTP status
- Custom exception classes (ToolExecutionError, AuthenticationError, InvalidInputError, etc.)

**Dependencies:** ErrorDetail model, LoggingUtility

**Technology Stack:** Python, Pydantic

**Module Location:** `src/utils/errors.py`

## Logging Utility Component

**Responsibility:** Configure structured JSON logging, bind correlation IDs to logger contexts, provide pre-configured loggers to components.

**Key Interfaces:**
- `configure_logging(log_level)` - Initialize structlog at startup
- `get_logger(name)` - Get module-specific logger
- `bind_correlation_id(correlation_id)` - Create request-scoped logger
- `sanitize_log_data(data)` - Remove sensitive fields

**Dependencies:** structlog, Python logging

**Technology Stack:** structlog

**Module Location:** `src/utils/logging.py`

## Health Check Handler Component

**Responsibility:** Provide Kubernetes liveness/readiness probe endpoint.

**Key Interfaces:**
- `async def health_check()` - Return health status
- `check_dependencies()` - Verify tool registry initialized

**Dependencies:** ToolRegistry, HealthCheckResponse model

**Technology Stack:** Python, Pydantic

**Module Location:** `src/handlers/health.py`

## Configuration Component

**Responsibility:** Load and validate configuration from environment variables.

**Key Interfaces:**
- `class Config(BaseSettings)` - Pydantic settings model
- `get_config()` - Singleton config instance

**Dependencies:** pydantic-settings, python-dotenv

**Technology Stack:** Pydantic BaseSettings

**Module Location:** `src/config.py`

---
