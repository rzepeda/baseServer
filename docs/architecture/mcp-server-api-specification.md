# MCP Server API Specification

## Base Information

**Base URL:**
- Local: `http://localhost:8080`
- Kubernetes (internal): `http://mcp-server:8080`
- Cloudflare Tunnel (public): `https://mcp-server.example.com`

**Protocol:** HTTP/1.1 (HTTPS enforced for public access)

**Content-Type:** `application/json`

**Authentication:** OAuth 2.0 Bearer Token (except `/health`)

## Endpoints

### POST /tools/invoke

**Purpose:** Invoke a registered MCP tool

**Authentication:** Required (OAuth 2.0 Bearer Token)

**Request:**
```json
{
  "tool": "get_youtube_transcript",
  "parameters": {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }
}
```

**Success Response (200 OK):**
```json
{
  "success": true,
  "result": "Never gonna give you up...",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "execution_time_ms": 1847
}
```

**Error Response (400 Bad Request):**
```json
{
  "success": false,
  "error": {
    "error_code": "invalid_url",
    "message": "Invalid YouTube URL format...",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Tool executed successfully |
| 400 | Invalid parameters |
| 401 | Missing or invalid OAuth token |
| 404 | Tool not found or transcript unavailable |
| 500 | Internal server error |
| 503 | External service unavailable |

### GET /health

**Purpose:** Kubernetes liveness/readiness probe

**Authentication:** None required

**Success Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-21T14:32:15.123Z",
  "version": "1.0.0",
  "registered_tools": ["get_youtube_transcript"]
}
```

## Error Code Reference

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `invalid_token` | 401 | OAuth token invalid or expired |
| `missing_token` | 401 | Authorization header not present |
| `invalid_url` | 400 | YouTube URL format invalid |
| `invalid_input` | 400 | Required parameters missing |
| `tool_not_found` | 404 | Requested tool not registered |
| `transcript_unavailable` | 404 | Video has no transcript |
| `video_not_found` | 404 | YouTube video does not exist |
| `network_error` | 503 | Failed to connect to YouTube |
| `youtube_api_error` | 503 | YouTube service error |
| `internal_error` | 500 | Unexpected server error |

---
