# Story: Configurable OAuth Middleware

**ID:** STORY-3  
**Epic:** EPIC-2 - Production Hardening & Kubernetes Deployment  
**Title:** Add `USE_OAUTH` environment variable to enable/disable OAuth middleware  
**Status:** DRAFT  

---

### 1. User Story

As a developer, I want to enable or disable OAuth 2.0 authentication via an environment variable, so that I can easily run the application in a local development environment without needing to set up a full OAuth provider.

### 2. Acceptance Criteria

1.  **Configuration:**
    *   A new environment variable `USE_OAUTH` is added to the configuration in `src/config.py`.
    *   It should be a boolean and default to `True`.
    *   The `.env.example` file is updated to include `USE_OAUTH=True`.

2.  **Conditional Middleware (MCP Server):**
    *   In `src/mcp_server.py`, the `OAuthMiddleware` is only applied if `USE_OAUTH` is `True`.
    *   If `USE_OAUTH` is `False`, the `app` should be the raw `mcp.app` (or `mcp.streamable_http_app()`).

3.  **Conditional Middleware (REST API Server):**
    *   In `src/server.py`, the `app.add_middleware(OAuthMiddleware, ...)` call is only executed if `USE_OAUTH` is `True`.

4.  **Logging:**
    *   When the server starts, it should log a clear message indicating whether OAuth middleware is enabled or disabled.

### 3. Technical Notes

*   This change will affect both the MCP server and the REST API server.
*   Care should be taken to ensure that when the middleware is disabled, the application still functions correctly.
*   This is primarily a development feature. In production environments, `USE_OAUTH` should always be `True`.

### 4. Definition of Done

*   All acceptance criteria are met.
*   The `test_mcp_flow.sh` script passes when `USE_OAUTH` is `False`.
*   The application starts without errors when `USE_OAUTH` is `True` (assuming valid OAuth configuration).
*   The changes are documented in the new story file.
*   The story is linked to Epic 2.
