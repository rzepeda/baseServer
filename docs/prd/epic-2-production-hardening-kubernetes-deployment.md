# Epic 2: Production Hardening & Kubernetes Deployment

**Epic Goal:** Secure the MCP server with OAuth authentication, add production logging, containerize for Kubernetes deployment, and create production-ready infrastructure for 24/7 availability.

---

## Story 2.1: OAuth 2.0 Authentication Implementation

**As a** security-conscious developer,
**I want** OAuth 2.0 authentication protecting all MCP tool endpoints,
**so that** only authorized clients (like Claude) can access the transcript service.

### Acceptance Criteria

1. `authlib` library added to project dependencies
2. OAuth configuration module created supporting:
   - OAuth provider endpoint URL (environment variable)
   - Client ID and client secret (environment variables)
   - Authorized scopes (configurable)
   - Token validation endpoint
3. Authentication middleware implemented that:
   - Extracts bearer token from Authorization header
   - Validates token with OAuth provider
   - Returns HTTP 401 for missing/invalid tokens
   - Returns HTTP 403 for expired tokens
   - Caches valid tokens briefly (60s) to reduce validation overhead
4. All MCP tool endpoints protected by authentication middleware
5. Health check endpoint (`/health`) remains unauthenticated for K8s probes
6. Error responses follow OAuth 2.0 error format:
   - `{"error": "invalid_token", "error_description": "..."}`
7. Security requirements enforced:
   - OAuth credentials never logged or exposed
   - Token validation completes in <500ms (per NFR14)
   - Failed auth attempts logged (username/client ID only, no tokens)
8. Environment variable template (`.env.example`) created documenting:
   - Required OAuth configuration variables
   - Example values (non-sensitive)
9. Unit tests covering:
   - Valid token acceptance
   - Invalid token rejection
   - Missing token rejection
   - Expired token handling
10. Integration test with mocked OAuth provider validates end-to-end flow
11. Successful manual test: Request with valid OAuth token succeeds, request without token returns 401

---

## Story 2.2: Enhanced Error Handling and Production Logging

**As a** developer debugging issues,
**I want** comprehensive error handling and structured logging,
**so that** I can quickly diagnose problems and monitor service health.

### Acceptance Criteria

1. Structured JSON logging implemented using `structlog` or similar:
   - All logs output to stdout/stderr as JSON
   - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
   - Each log includes: timestamp, level, message, correlation ID, context
2. Request correlation IDs added:
   - Generate unique ID for each incoming request
   - Include in all log messages for that request
   - Return in response header (`X-Correlation-ID`)
3. Enhanced error handling for YouTube tool:
   - Network timeouts (5s limit) with retry logic (max 2 retries)
   - Rate limiting detection with helpful error message
   - Region-locked video detection
   - Age-restricted content handling
   - Malformed video ID edge cases
4. Error response standardization:
   - Consistent JSON format: `{"error": "error_code", "message": "human-readable", "correlation_id": "..."}`
   - HTTP status codes match error types (400 client errors, 500 server errors, 503 service unavailable)
5. Performance logging:
   - Log request duration for all tool invocations
   - Log transcript fetch time separately
   - Warn if response time exceeds 5s threshold (NFR1)
6. Security logging:
   - Log all authentication attempts (success/failure)
   - Log OAuth token validation failures
   - Never log sensitive data (tokens, credentials, PII)
7. Startup logging includes:
   - Server version/commit hash
   - Registered tools count and names
   - Configuration summary (non-sensitive)
8. Unit tests for error scenarios and logging output format
9. Documentation updated with:
   - Log format specification
   - Error code reference table
   - Troubleshooting guide using logs
10. Successful manual test: Trigger various error scenarios, verify structured logs contain actionable information with correlation IDs

---

## Story 2.3: Docker Containerization and Kubernetes Deployment

**As a** developer,
**I want** the MCP server packaged as a Docker container and deployed to Kubernetes,
**so that** I have a production-ready, always-available service independent of my local machine.

### Acceptance Criteria

1. `Dockerfile` created with:
   - Base image: `python:3.11-slim` or `python:3.11-alpine`
   - COPY application code and dependencies
   - RUN pip install from requirements file
   - EXPOSE port 8080
   - CMD to start MCP server
   - Non-root user for security
2. `.dockerignore` file excludes unnecessary files (tests, docs, .git, etc.)
3. Docker image builds successfully and is <200MB in size
4. Kubernetes manifests created in `k8s/` directory:
   - **Deployment:** 1-2 replicas, resource limits (512MB memory), health checks configured
   - **Service:** ClusterIP type exposing port 8080
   - **Secret template:** For OAuth credentials (`.env` to Secret conversion documented)
   - Environment variable configuration via ConfigMap/Secrets
5. Health check probes configured:
   - Liveness probe: HTTP GET /health (every 30s)
   - Readiness probe: HTTP GET /health (every 10s)
   - Startup probe for initial bootstrap
6. OAuth configuration integrated:
   - Kubernetes Secret for OAuth client credentials
   - Environment variables mounted into pod
   - Documentation for creating secrets from values
7. Deployment documentation updated with:
   - Docker build and push instructions (local registry or Docker Hub)
   - Kubernetes Secret creation for OAuth
   - Kubernetes deployment commands (`kubectl apply`)
   - How to verify deployment status
   - How to view logs (`kubectl logs`)
   - How to test via port-forward before tunnel integration
8. Rollout and update strategy:
   - Rolling update configured
   - Max unavailable: 0 (zero-downtime updates)
   - Rollback procedure documented
9. Successful manual test sequence:
   - Build Docker image locally
   - Create Kubernetes Secrets with OAuth credentials
   - Deploy to local K8s cluster
   - Verify pods start and pass health checks
   - Port-forward to local machine
   - Use MCP client with OAuth token to retrieve transcript
   - Verify OAuth rejection for invalid token
   - Check structured logs in pod output
10. All tests pass in containerized K8s environment

---

## Story 2.4: Kubernetes Tunnel Integration and End-to-End Production Testing

**As a** production user,
**I want** the Kubernetes-deployed MCP server accessible via Cloudflare Tunnel with full OAuth protection,
**so that** I have a secure, always-available service I can use from anywhere.

### Acceptance Criteria

1. Cloudflare Tunnel Kubernetes deployment created:
   - `k8s/cloudflare-tunnel.yaml` manifest with Deployment for `cloudflared`
   - ConfigMap for tunnel configuration (routes to MCP Service ClusterIP)
   - Secret for tunnel credentials (documented how to create from local tunnel)
   - Resource limits for tunnel container
2. Tunnel configuration updated:
   - Points to K8s Service name (e.g., `http://mcp-server:8080`)
   - HTTPS enforced at tunnel edge
   - Same public hostname as Epic 1 (or new production hostname)
3. Deployment options documented:
   - **Recommended:** Separate Deployment for tunnel (easier to manage)
   - **Alternative:** Sidecar container (tighter coupling)
   - Rationale for recommendation provided
4. Tunnel health monitoring:
   - Tunnel pod logs show successful connection to Cloudflare
   - Cloudflare dashboard shows tunnel as healthy
   - DNS still resolves correctly to tunnel
5. End-to-end integration test suite created:
   - Simulates Claude/MCP client requests via tunnel
   - Tests OAuth authentication flow (valid token, invalid token, missing token)
   - Tests YouTube transcript retrieval (success, errors)
   - Tests health endpoint accessibility (unauthenticated)
   - Can run against production K8s deployment
6. Performance validation against NFRs:
   - Load test with 10 concurrent requests maintains <5s response time
   - Memory usage stays under 512MB per pod
   - OAuth token validation <500ms
   - Error rate <5% under normal conditions
7. Production readiness checklist validated:
   - ✅ OAuth protecting all tool endpoints
   - ✅ Health endpoint unauthenticated for K8s
   - ✅ Structured JSON logging to stdout
   - ✅ No secrets in code/configs
   - ✅ HTTPS enforced for remote access
   - ✅ Kubernetes resource limits configured
   - ✅ Health probes working
   - ✅ Zero-downtime rolling updates configured
8. Complete documentation in README:
   - Architecture diagram (local dev vs K8s production)
   - Full deployment guide (from scratch to production)
   - Daily operations (view logs, update deployment, rollback)
   - Monitoring and troubleshooting
   - How to add new tools to the registry
9. Migration guide from Epic 1 to Epic 2:
   - How to transition from local + tunnel to K8s + tunnel
   - OAuth configuration differences
   - Claude/MCP client reconfiguration (if needed)
   - Testing both deployments in parallel
10. Successful production acceptance test:
    - Fresh K8s deployment following documentation
    - Cloudflare Tunnel connecting successfully
    - Claude retrieves transcript via public URL with OAuth
    - Invalid auth rejected properly
    - Service survives pod restart (K8s reschedules)
    - Logs provide actionable debugging information
## Story 2.5: Configurable OAuth Middleware

**As a** developer,
**I want** to enable or disable OAuth 2.0 authentication via an environment variable,
**so that** I can easily run the application in a local development environment without needing to set up a full OAuth provider.

See [STORY-3: Configurable OAuth Middleware](../../docs/stories/story_configurable_oauth.md)

---
