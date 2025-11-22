# Data Models

**Note:** This is a **stateless service with no persistent database** (per PRD NFR10, NFR12). The models below are **in-memory Python data structures** (using `dataclasses` or `pydantic` models) representing runtime objects, MCP protocol messages, and tool registration metadata.

## MCPToolDefinition

**Purpose:** Represents a registered MCP tool's metadata in the tool registry. Each tool (YouTube, future Vimeo, etc.) creates one instance at server startup.

**Key Attributes:**
- `name`: str - Unique tool identifier (e.g., "get_youtube_transcript")
- `description`: str - Human-readable tool description for MCP schema
- `input_schema`: dict - JSON Schema defining tool input parameters
- `handler`: Callable - Async function that executes tool logic
- `version`: str - Tool version for API evolution (default "1.0")

**Relationships:**
- Registered with `ToolRegistry` at server startup
- Handler invoked by MCP server when tool is called

## MCPRequest

**Purpose:** Represents an incoming MCP tool invocation request from a client (e.g., Claude).

**Key Attributes:**
- `tool_name`: str - Name of tool to invoke
- `parameters`: dict - Tool-specific input parameters
- `correlation_id`: str - Unique request ID for log tracing
- `auth_context`: Optional[AuthContext] - OAuth validation result

## MCPResponse

**Purpose:** Represents a tool execution result returned to the MCP client.

**Key Attributes:**
- `success`: bool - Whether tool execution succeeded
- `result`: Optional[Any] - Tool output data (if successful)
- `error`: Optional[ErrorDetail] - Error information (if failed)
- `correlation_id`: str - Matches request correlation ID
- `execution_time_ms`: int - Execution duration for performance monitoring

## ErrorDetail

**Purpose:** Standardized error information structure for consistent error responses.

**Key Attributes:**
- `error_code`: str - Machine-readable error code
- `message`: str - Human-readable error description
- `details`: Optional[dict] - Additional context
- `correlation_id`: str - Request correlation ID for log lookup

## AuthContext

**Purpose:** OAuth token validation result, attached to authenticated requests.

**Key Attributes:**
- `is_valid`: bool - Whether token passed validation
- `token_hash`: str - SHA256 hash of token (for logging, never log raw token)
- `scopes`: list[str] - OAuth scopes granted by token
- `expires_at`: Optional[datetime] - Token expiration time
- `client_id`: Optional[str] - OAuth client identifier

## YouTubeTranscriptEntry

**Purpose:** Represents a single transcript segment from YouTube's transcript data.

**Key Attributes:**
- `text`: str - Transcript text content
- `start`: float - Start time in seconds
- `duration`: float - Segment duration in seconds

## YouTubeURL

**Purpose:** Parsed YouTube URL with extracted video ID.

**Key Attributes:**
- `raw_url`: str - Original URL provided by user
- `video_id`: str - Extracted YouTube video ID (11 characters)
- `url_format`: str - Detected format ("youtube.com" or "youtu.be")

## ToolExecutionContext

**Purpose:** Runtime context passed to tool handlers containing request metadata and utilities.

**Key Attributes:**
- `correlation_id`: str - Request correlation ID
- `logger`: structlog.BoundLogger - Logger with correlation ID pre-bound
- `auth_context`: AuthContext - OAuth validation result
- `start_time`: datetime - Request start time for duration calculation

## HealthCheckResponse

**Purpose:** Simple health check status for Kubernetes probes.

**Key Attributes:**
- `status`: str - "healthy" or "unhealthy"
- `timestamp`: datetime - Health check time
- `version`: str - Server version/commit hash
- `registered_tools`: list[str] - Names of registered tools

---
