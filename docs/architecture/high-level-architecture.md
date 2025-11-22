# High Level Architecture

## Technical Summary

The youtubeagenttranscript system is a **stateless, plugin-based MCP server** built in Python 3.12+, exposing YouTube transcript retrieval as an MCP-native tool for AI agents like Claude. The architecture uses a **tool registry pattern** to enable extensible tool addition (future Vimeo, TikTok, podcast support) without server restructuring. Core components include: MCP protocol handler (using official Anthropic SDK), OAuth 2.0 middleware (authlib), tool registry with dynamic schema generation, and pluggable tool modules (YouTube via youtube-transcript-api). The system is containerized with Docker, deployed to Kubernetes, and exposed via Cloudflare Tunnel for secure remote access, directly supporting the PRD's goals of zero-friction MCP integration, self-hosted deployment with remote access, and extensible multi-platform architecture.

## High Level Overview

**1. Architectural Style: Plugin-Based Stateless Service**

A single containerized Python application with an extensible tool registry system. Not a traditional microservices architecture, but rather a **modular monolith with runtime plugin registration**. Each tool (e.g., YouTube, future platforms) is an independent module implementing a standard interface, registered at server startup.

**2. Repository Structure: Monorepo**

Single Git repository containing:
- Python MCP server code (src/)
- Tool implementations (src/tools/)
- Kubernetes manifests (k8s/)
- Dockerfile and container configuration
- Documentation (docs/)
- Tests (tests/)

**3. Service Architecture: Single MCP Server with Tool Registry**

One Python process handling:
- MCP protocol communication
- OAuth 2.0 bearer token validation
- HTTP health check endpoint
- Dynamic tool registration and invocation routing
- Structured JSON logging

**4. Primary User Interaction Flow:**

```
User (Claude)
  → Cloudflare Tunnel (HTTPS, public URL)
    → Kubernetes Service (ClusterIP)
      → MCP Server Pod (OAuth validation)
        → Tool Registry (route to handler)
          → YouTube Tool (youtube-transcript-api)
            → YouTube API (transcript extraction)
              → Response (transcript text)
```

**5. Key Architectural Decisions:**

| Decision | Rationale |
|----------|-----------|
| **Python over TypeScript/Go** | Mature youtube-transcript-api library, official MCP Python SDK, excellent OAuth ecosystem (authlib), team familiarity |
| **Tool Registry Pattern** | Enables adding Vimeo/TikTok/podcasts without refactoring core server; minimal overhead now vs. major work later |
| **Stateless Design (No Database)** | Simplifies deployment, enables horizontal scaling, meets NFR12; transcripts fetched on-demand per PRD scope |
| **OAuth 2.0 (not API keys)** | Matches Claude's native auth flow, industry-standard security, token expiration/revocation support |
| **Cloudflare Tunnel (not ngrok/Tailscale)** | Zero-trust architecture, free tier sufficient, automatic HTTPS, K8s-friendly, reliable uptime |
| **Kubernetes (not serverless)** | Local cluster control, no cold starts (NFR1: <5s response), simpler OAuth integration, 99%+ uptime (NFR4) |

## High Level Project Diagram

```mermaid
graph TB
    User[Claude/MCP Client]

    subgraph Internet
        Tunnel[Cloudflare Tunnel<br/>HTTPS Public URL]
    end

    subgraph Kubernetes Cluster
        TunnelPod[cloudflared Pod]
        Service[MCP Server Service<br/>ClusterIP:8080]

        subgraph MCP Server Pod
            OAuth[OAuth 2.0 Middleware]
            MCP[MCP Protocol Handler]
            Registry[Tool Registry]

            subgraph Tools
                YT[YouTube Tool]
                Future1[Future: Vimeo Tool]
                Future2[Future: Podcast Tool]
            end
        end

        Health[/health endpoint]
    end

    subgraph External Services
        YouTube[YouTube API<br/>youtube-transcript-api]
        OAuthProvider[OAuth Provider<br/>Token Validation]
    end

    User -->|HTTPS Request + OAuth Token| Tunnel
    Tunnel --> TunnelPod
    TunnelPod --> Service
    Service --> OAuth
    OAuth -->|Validate Token| OAuthProvider
    OAuth -->|Authorized| MCP
    MCP --> Registry
    Registry -->|Route to Tool| YT
    YT -->|Fetch Transcript| YouTube

    Service -.->|K8s Probes| Health

    Future1 -.->|Phase 2| Registry
    Future2 -.->|Phase 2| Registry

    style YT fill:#90EE90
    style Future1 fill:#FFE4B5
    style Future2 fill:#FFE4B5
    style OAuth fill:#FFA07A
```

## Architectural and Design Patterns

**1. Service Architecture Pattern: Plugin-Based Monolith (Recommended)**

- Single Python process with tool registry for runtime plugin loading
- Tools share process, memory, and infrastructure
- _Rationale:_ Personal project with 1-5 tools expected; microservices overhead unjustified; PRD specifies single containerized server; simpler to operate and maintain; can refactor to microservices later if tool count exceeds 10+

**2. Tool Registration Pattern: Abstract Base Class with Runtime Registry**

- Each tool extends `BaseMCPTool` abstract class
- Tools register themselves in a centralized `ToolRegistry` on import
- Registry validates schema and provides lookup by tool name
- _Rationale:_ Enforces interface contract, enables dynamic schema generation for MCP, type-safe in Python with protocols/ABC, testable in isolation

**3. Authentication Pattern: Middleware-Based OAuth 2.0 Bearer Token Validation**

- ASGI/WSGI middleware intercepts all requests before tool invocation
- Extracts Authorization header, validates bearer token with OAuth provider
- Returns 401 for missing/invalid tokens before reaching MCP handler
- _Rationale:_ Separation of concerns (auth vs. business logic), consistent enforcement across all tools, matches Claude's OAuth flow per PRD

**4. Communication Pattern: Request/Response (Synchronous HTTP)**

- MCP tools exposed via HTTP endpoints using official MCP SDK
- Client sends tool invocation request, server responds with result
- No WebSockets, no streaming (MVP scope)
- _Rationale:_ Aligns with MCP protocol specification, simpler than async/streaming, meets <5s response time requirement for transcripts

**5. Error Handling Pattern: Structured Exception Hierarchy with Correlation IDs**

- Custom exception classes (e.g., `ToolExecutionError`, `AuthenticationError`, `YouTubeAPIError`)
- Global exception handler converts to standardized JSON responses
- Every request gets unique correlation ID for log tracing
- _Rationale:_ Consistent error format for MCP clients, debuggability via logs, follows PRD Story 2.2 requirements

**6. Logging Pattern: Structured JSON Logging (stdout/stderr)**

- All logs output as JSON with: timestamp, level, message, correlation_id, context
- Uses structlog library for structured log building
- Kubernetes captures stdout/stderr for centralized log aggregation
- _Rationale:_ Machine-parseable for monitoring tools, correlation ID tracing, K8s-native pattern, meets NFR requirements

**7. Configuration Management Pattern: 12-Factor Environment Variables**

- All configuration via environment variables (OAuth credentials, ports, endpoints)
- Kubernetes Secrets for sensitive data (OAuth client secret, tunnel token)
- ConfigMaps for non-sensitive config
- _Rationale:_ Cloud-native best practice, K8s-friendly, no secrets in code/images, environment-specific config

**8. Deployment Pattern: Tunnel as Separate Deployment (Recommended)**

- Cloudflare Tunnel runs in separate K8s Deployment
- Routes to MCP Server Service via internal ClusterIP
- _Rationale:_ Operational flexibility, tunnel issues don't affect server health checks, aligns with PRD's recommendation in Story 2.4, minimal resource overhead difference

---
