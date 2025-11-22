# Database Schema

**No persistent database required for this architecture.**

This MCP server follows a **fully stateless design** per PRD requirements NFR10 and NFR12.

**Data Storage Strategy:**

| Data Type | Storage Approach | Lifetime |
|-----------|-----------------|----------|
| YouTube Transcripts | Not stored | Request-only |
| OAuth Tokens | In-memory cache only | 60 seconds |
| Request Correlation IDs | Logs only (stdout) | Until log rotation |
| Tool Registry | In-memory (loaded at startup) | Server lifetime |
| Server Configuration | Environment variables | Server lifetime |

---
