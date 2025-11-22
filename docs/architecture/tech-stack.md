# Tech Stack

## Cloud Infrastructure

- **Provider:** Local Kubernetes Cluster (k3s/minikube/kind for development, standard K8s for production)
- **Key Services:**
  - Kubernetes (container orchestration, health probes, service discovery)
  - Cloudflare Tunnel (remote access, automatic HTTPS, zero-trust networking)
- **Deployment Regions:** Local cluster (user's infrastructure)

## Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
|----------|-----------|---------|---------|-----------|
| **Language** | Python | 3.12 | Primary development language | Stable release, excellent library ecosystem, async support, MCP SDK compatibility |
| **Runtime** | CPython | 3.12 | Python interpreter | Standard implementation, best compatibility |
| **ASGI Server** | Uvicorn | 0.30+ | HTTP server for MCP endpoints | Industry standard for async Python, production-ready, lightweight, excellent performance |
| **MCP SDK** | mcp (Anthropic) | Latest | MCP protocol implementation | Official SDK, handles protocol details, schema generation support |
| **YouTube Library** | youtube-transcript-api | 0.6+ | Transcript extraction | Mature, actively maintained, handles multiple transcript scenarios, no API key required |
| **OAuth Library** | authlib | 1.3+ | OAuth 2.0 token validation | Standards-compliant, supports bearer tokens, widely used, secure |
| **Logging** | structlog | 24.1+ | Structured JSON logging | Machine-parseable logs, correlation ID support, K8s-friendly stdout logging |
| **HTTP Client** | httpx | 0.27+ | HTTP requests (OAuth validation) | Async support, modern API, better than requests for async contexts |
| **Testing Framework** | pytest | 8.0+ | Unit and integration testing | Industry standard, rich plugin ecosystem, fixture support |
| **Test Mocking** | pytest-mock | 3.12+ | Mocking for unit tests | Simplifies mocking, integrates with pytest |
| **Async Testing** | pytest-asyncio | 0.23+ | Testing async code | Required for async test cases with Uvicorn/ASGI |
| **Code Formatter** | black | 24.0+ | Automatic code formatting | Opinionated formatter, eliminates style debates, AI-agent friendly |
| **Linter** | ruff | 0.3+ | Fast Python linter | Replaces flake8/pylint/isort, extremely fast, comprehensive rules |
| **Type Checker** | mypy | 1.9+ | Static type checking | Catches type errors, improves code quality, IDE support |
| **Container Base** | python:3.12-slim | 3.12 | Docker base image | Debian-based, ~150MB, production-ready, avoids Alpine C-extension issues |
| **Container Runtime** | Docker | 24+ | Container building and local testing | Industry standard, K8s-compatible images |
| **Orchestration** | Kubernetes | 1.28+ | Container orchestration | Health probes, service discovery, rolling updates, declarative deployment |
| **Tunnel Solution** | Cloudflare Tunnel (cloudflared) | Latest | Remote HTTPS access | Zero-trust networking, free tier, automatic TLS, K8s-friendly |
| **Package Manager** | pip | 24+ | Python dependency management | Standard tool, pyproject.toml support |
| **Build Tool** | pyproject.toml | N/A | Modern Python project config | PEP 518 standard, consolidates dependencies and tool config |
| **Dependency Management** | pip-tools | 7+ | Lock file generation (pip-compile) | Reproducible builds, separates abstract deps from pinned versions |

## Development Tools

| Category | Technology | Version | Purpose | Rationale |
|----------|-----------|---------|---------|-----------|
| **Version Control** | Git | 2.40+ | Source control | Industry standard |
| **Container Registry** | Docker Hub / Local | N/A | Image storage | Free tier sufficient, or local registry for privacy |
| **IDE Support** | Python Language Server | N/A | Editor integration | VSCode, PyCharm support for type hints and linting |

## Configuration & Secrets

- **Configuration Method:** Environment variables (12-factor app pattern)
- **Development Secrets:** `.env` file (gitignored) loaded via python-dotenv
- **Production Secrets:** Kubernetes Secrets for OAuth credentials, tunnel tokens
- **Non-sensitive Config:** Kubernetes ConfigMaps for ports, URLs, log levels

## 🚨 CRITICAL: This Tech Stack is Definitive

**All development agents, documentation, and implementation MUST use these exact technologies and versions.**

Any deviation requires:
1. Architecture document update
2. Explicit approval
3. Justification for the change

---
