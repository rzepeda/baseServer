# Error Handling Strategy

## General Approach

**Error Model:** Structured Exception Hierarchy with Standardized Error Responses

**Core Principles:**
1. Fail Fast - Validate inputs early
2. Fail Gracefully - Convert all exceptions to user-friendly messages
3. Never Fail Silently - All errors logged with full context
4. Security First - No sensitive data in errors or logs
5. Correlation Traceability - Every error includes correlation_id

## Exception Hierarchy

```python
class MCPServerError(Exception):
    """Base exception for all MCP server errors"""

class ClientError(MCPServerError):
    """Client-side errors (400-level)"""
    http_status = 400

class InvalidInputError(ClientError):
    """Invalid parameters"""

class InvalidURLError(ClientError):
    """Invalid YouTube URL"""

class AuthenticationError(MCPServerError):
    """OAuth authentication failed (401)"""
    http_status = 401

class ResourceNotFoundError(ClientError):
    """Resource not found (404)"""
    http_status = 404

class ServerError(MCPServerError):
    """Server-side errors (500-level)"""
    http_status = 500

class ExternalServiceError(ServerError):
    """External service unavailable (503)"""
    http_status = 503
```

## Logging Standards

**Library:** structlog (structured JSON logging)

**Format:** Every log entry is JSON to stdout/stderr

**Log Levels:**
- **DEBUG:** Detailed diagnostic information
- **INFO:** Normal operation events
- **WARNING:** Recoverable issues, degraded performance
- **ERROR:** Error conditions that were handled
- **CRITICAL:** Severe errors requiring immediate attention

**Required Context:**
- `correlation_id` - UUID per request (mandatory)
- `timestamp` - ISO 8601 format
- `level` - Log level
- `event` - Short event name

**NEVER LOG:**
- Raw OAuth tokens (hash only)
- OAuth client secrets
- Authorization headers
- User PII

## Error Handling Patterns

**Retry Policy (YouTube API):**
- Max 2 retries
- Exponential backoff: 1s, 2s
- Only retry transient errors (timeouts, 429, 503)
- Never retry permanent errors (400, 404, 401)

**Timeout Configuration:**
- YouTube transcript fetch: 5s
- OAuth token validation: 500ms
- Health check: 3s

**Error Response Format:**
```json
{
  "success": false,
  "error": {
    "error_code": "string",
    "message": "string",
    "details": {},
    "correlation_id": "uuid"
  },
  "execution_time_ms": 123
}
```

---
