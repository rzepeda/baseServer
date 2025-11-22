# Technical Assumptions

## Repository Structure: Monorepo

Single repository containing MCP server code, Dockerfile, Kubernetes manifests, and documentation.

## Service Architecture: Extensible Multi-Tool MCP Server

**Description:** Single containerized MCP server with plugin-style tool registration system. Each tool (e.g., YouTube transcripts, future Vimeo/TikTok/podcast tools) implemented as independent module that registers with the MCP server on startup.

**Architecture Pattern:**
- Core MCP server framework handles OAuth, health checks, logging, MCP protocol
- Tool registry/plugin system for registering new tools
- Each tool implements standard interface (schema, handler function, validation)
- MVP ships with one tool (YouTube), architected for easy additions

**Rationale:**
- Minimal overhead to build extensibility now vs. major refactor later
- Keeps tools isolated and testable independently
- Aligns with long-term vision for multiple video platforms
- Personal project benefit: Add new tools as needed without infrastructure changes

## Testing Requirements: Unit + Integration Testing

- **Unit Tests:** Core transcript extraction logic, URL parsing, error handling functions
- **Integration Tests:** Full MCP tool workflow, OAuth token validation, YouTube API interaction
- **Manual Testing:** End-to-end validation with Claude/MCP client
- **No E2E Automation:** Not required for MVP/personal use

## Programming Language & Framework

**Python 3.11+** with official Anthropic MCP Python SDK

**Rationale:**
- Mature `youtube-transcript-api` library is well-maintained and reliable
- Official MCP Python SDK available and documented
- Excellent OAuth library support (`authlib`)
- Strong ecosystem for containerization and API development

## YouTube Transcript Library

**`youtube-transcript-api`** (Python package)

**Rationale:** Popular, actively maintained, handles multiple transcript scenarios

## Tunnel Solution

**Cloudflare Tunnel** (cloudflared)

**Rationale:**
- Zero-trust architecture with automatic HTTPS
- Free tier meets requirements
- Easy integration with K8s (sidecar or separate deployment)
- Reliable uptime and performance

## Additional Technical Assumptions

- **Container Base Image:** Python 3.11-slim or Alpine for minimal attack surface and size
- **OAuth 2.0 Library:** `authlib` for standards-compliant OAuth implementation
- **MCP SDK:** Official `mcp` Python package from Anthropic
- **Deployment Target:** Existing Kubernetes cluster (k3s/minikube/standard k8s)
- **Configuration Management:** Environment variables for all secrets (OAuth credentials, Cloudflare tunnel token)
- **Logging Strategy:** Structured JSON logs to stdout/stderr for Kubernetes log aggregation
- **Health Check Endpoint:** HTTP `/health` endpoint for K8s liveness/readiness probes
- **No Persistent Storage:** Fully stateless - transcripts retrieved on-demand, not cached (MVP scope)
- **No Database Required:** All state managed via OAuth tokens and request/response cycle
- **Horizontal Scaling Ready:** Stateless design allows K8s Deployment with multiple replicas if needed

---
