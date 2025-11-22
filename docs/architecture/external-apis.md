# External APIs

## YouTube Transcript API (via youtube-transcript-api)

**Purpose:** Retrieve official YouTube video transcripts/captions without requiring API keys.

**Documentation:**
- Library: https://github.com/jdepoix/youtube-transcript-api
- PyPI: https://pypi.org/project/youtube-transcript-api/

**Base URL(s):** The `youtube-transcript-api` library abstracts the actual YouTube endpoints (undocumented API)

**Authentication:** None required

**Rate Limits:** No official rate limits published; recommend client-side rate limiting (max 10 requests/minute)

**Integration Notes:**

**Error Scenarios:**

| Error Type | Library Exception | Our Error Code | HTTP Status | Handling |
|------------|------------------|----------------|-------------|----------|
| Video not found | `VideoUnavailable` | `video_not_found` | 404 | Return clear error |
| No transcript available | `NoTranscriptFound` | `transcript_unavailable` | 404 | Return error with explanation |
| Invalid video ID | `InvalidVideoId` | `invalid_url` | 400 | Return validation error |
| Network timeout | `requests.Timeout` | `network_error` | 503 | Retry up to 2 times |
| Rate limited | Various (403/429) | `youtube_api_error` | 503 | Retry with backoff |

**Performance:** Average 1-3 seconds, 5s timeout configured (NFR1)

**Compliance:** Personal use allowed under YouTube TOS; no redistribution or storage

## OAuth 2.0 Token Validation Service

**Purpose:** Validate OAuth 2.0 bearer tokens provided by MCP clients (Claude).

**Documentation:** OAuth 2.0 Token Introspection (RFC 7662)

**Base URL(s):** Configured via `OAUTH_TOKEN_ENDPOINT` environment variable

**Authentication:** Client credentials (client ID and client secret)

**Rate Limits:** Unknown; mitigated with 60-second token cache

**Integration Notes:**

Token validation cached for 60 seconds (in-memory) to reduce OAuth provider load and improve performance (NFR14: <500ms).

**Error Scenarios:**

| Error Type | HTTP Status | Our Handling |
|------------|-------------|--------------|
| Invalid token | 200 OK (active=false) | Return 401 to client |
| OAuth provider down | 503 Service Unavailable | Return 503, log error |
| Timeout (>500ms) | Timeout exception | Return 503, log warning |

**Performance:** Target <500ms validation time (NFR14); cache hit <1ms

---
