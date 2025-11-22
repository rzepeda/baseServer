# Epic 1: Local MCP Server & Remote Access Validation

**Epic Goal:** Build a working, extensible MCP server with YouTube transcript extraction running on your local machine, accessible remotely via Cloudflare Tunnel so you can start using it with Claude immediately.

---

## Story 1.1: Python Project Setup and MCP Server Bootstrap

**As a** developer,
**I want** a properly initialized Python project with MCP SDK integration,
**so that** I have a solid foundation for building the extensible MCP server.

### Acceptance Criteria

1. Python project structure created with standard layout (src/, tests/, docs/, etc.)
2. `pyproject.toml` or `requirements.txt` configured with:
   - Python 3.11+ specified
   - Official Anthropic MCP Python SDK (`mcp`)
   - `youtube-transcript-api`
   - Testing framework (pytest)
   - Logging libraries (structlog or similar for JSON logging)
3. Basic MCP server application created that:
   - Initializes MCP server instance
   - Starts and listens on configurable port (default 8080)
   - Logs startup message with structured JSON format
4. HTTP health check endpoint (`/health`) implemented returning 200 OK with JSON status
5. Git repository initialized with `.gitignore` for Python projects
6. README.md created with project overview and setup instructions
7. Application can be started locally via `python -m src.main` (or similar entry point)
8. Successful manual test: Server starts, health endpoint returns 200

---

## Story 1.2: Extensible Tool Registry and Plugin System

**As a** developer,
**I want** a tool registration system that supports multiple MCP tools,
**so that** I can easily add new tools (Vimeo, TikTok, podcasts) without restructuring the server.

### Acceptance Criteria

1. Tool registry module created with:
   - `ToolRegistry` class for managing registered tools
   - `register_tool()` method accepting tool definitions
   - `get_tools()` method returning all registered tools for MCP schema
2. Base tool interface/abstract class defined specifying:
   - Tool name (string)
   - Tool description (string)
   - Input schema (JSON schema for parameters)
   - Handler function signature (accepts params, returns result)
3. Registry validates tool definitions on registration:
   - Required fields present (name, description, schema, handler)
   - No duplicate tool names
   - Input schema is valid JSON schema
4. MCP server modified to:
   - Initialize tool registry on startup
   - Dynamically generate MCP tools schema from registered tools
   - Route tool invocations to correct handler via registry
5. Unit tests created for:
   - Tool registration success/failure scenarios
   - Tool retrieval and lookup
   - Duplicate tool name rejection
6. Documentation added explaining how to create and register new tools
7. Successful manual test: Server starts with empty registry, exposes no tools via MCP

---

## Story 1.3: YouTube Transcript Extraction Tool Implementation

**As a** user with Claude/MCP client,
**I want** to provide a YouTube URL and receive the video transcript,
**so that** I can analyze video content without watching.

### Acceptance Criteria

1. YouTube tool module created (`youtube_tool.py` or similar) implementing:
   - Tool name: "get_youtube_transcript"
   - Tool description: Clear explanation of functionality
   - Input schema: Single parameter `url` (string, YouTube URL)
   - Handler function that extracts and returns transcript
2. URL validation logic:
   - Accepts `youtube.com/watch?v=...` format
   - Accepts `youtu.be/...` format
   - Extracts video ID from URL
   - Returns clear error for invalid URLs
3. Transcript extraction using `youtube-transcript-api`:
   - Retrieve available transcripts for video ID
   - Return transcript text as formatted string
   - Handle missing transcripts gracefully (error message)
4. Error handling for common scenarios:
   - Invalid URL format → "Invalid YouTube URL provided"
   - Video not found → "YouTube video not found"
   - No transcript available → "No transcript available for this video"
   - Network/API errors → "Failed to retrieve transcript: [reason]"
5. Tool registered with tool registry on server startup
6. Unit tests covering:
   - URL parsing for both formats
   - Successful transcript retrieval (mocked API)
   - All error scenarios
7. Integration test with real YouTube video (public, known to have transcript)
8. Successful manual test: Use MCP client to request transcript for valid YouTube URL, receive complete transcript text

---

## Story 1.4: Cloudflare Tunnel Setup for Local Development

**As a** remote user,
**I want** to access my locally-running MCP server via Cloudflare Tunnel,
**so that** I can validate tunnel connectivity and use the transcript tool with Claude from anywhere before investing in Kubernetes deployment.

### Acceptance Criteria

1. Cloudflare account and domain prerequisites documented in README
2. Cloudflare Tunnel created via `cloudflared` CLI:
   - Tunnel registered with Cloudflare account
   - Tunnel credentials downloaded and stored securely
   - Tunnel configuration file created pointing to `localhost:8080`
3. `cloudflared` tunnel configuration (`cloudflare-tunnel.yml` or similar) created with:
   - Ingress rules routing public hostname to local server
   - HTTPS enforced (HTTP redirects to HTTPS)
   - No authentication at tunnel level (will add OAuth in Epic 2)
4. Local tunnel startup documented:
   - Command to start `cloudflared` tunnel daemon
   - How to verify tunnel status
   - How to check tunnel logs
5. DNS configuration completed:
   - CNAME record pointing to tunnel endpoint
   - DNS propagation verified
6. Tunnel connectivity validated:
   - Public HTTPS URL accessible from external network
   - Health endpoint (`/health`) returns 200 via tunnel
   - No certificate warnings (Cloudflare-managed cert)
7. End-to-end YouTube transcript test:
   - Start local Python MCP server
   - Start Cloudflare Tunnel pointing to local server
   - Configure Claude/MCP client with public tunnel URL
   - Successfully retrieve YouTube transcript remotely
8. Documentation added covering:
   - One-time Cloudflare Tunnel setup steps
   - Daily usage workflow (start server → start tunnel)
   - Troubleshooting common tunnel issues
   - Security note: No auth yet, don't share URL publicly
9. Known limitations documented:
   - No OAuth protection yet (Epic 2)
   - Tunnel depends on local machine being online
   - Public URL should be kept private until auth added
10. Successful manual test: Access tool from phone/laptop on different network, retrieve transcript via Claude

---
