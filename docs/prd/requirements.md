# Requirements

## Functional Requirements

**FR1:** Accept YouTube video URLs in standard formats (youtube.com/watch?v=..., youtu.be/...) as input parameter

**FR2:** Retrieve official YouTube transcripts/captions using available extraction methods (API or library-based)

**FR3:** Expose transcript extraction functionality as MCP-compliant tool with proper schema definition including tool name, description, and input parameters

**FR4:** Return complete transcript text in readable format to calling AI agent

**FR5:** Provide clear, actionable error messages for common failure scenarios (invalid URL, transcript unavailable, service errors, rate limiting)

**FR6:** Package application as Docker container with minimal base image (Alpine or distroless)

**FR7:** Provide Kubernetes deployment manifests (Pod/Deployment, Service) for local cluster deployment

**FR8:** Support remote access via Cloudflare Tunnel with documented configuration

**FR9:** Include health check endpoint for Kubernetes liveness/readiness probes

**FR10:** Support OAuth 2.0 authentication for all MCP tool requests compatible with Claude's authentication flow

**FR11:** Reject unauthenticated requests with appropriate HTTP 401 responses and OAuth error messages

**FR12:** Support OAuth configuration via environment variables (client ID, client secret, token endpoint, authorized scopes)

**FR13:** Validate OAuth bearer tokens on each request before processing

**FR14:** Support extensible tool registration architecture allowing multiple MCP tools to be exposed from the same server

**FR15:** YouTube transcript tool must be implemented as a pluggable module that can coexist with future tools

## Non-Functional Requirements

**NFR1:** Transcript retrieval must complete in <5 seconds for videos up to 60 minutes in length

**NFR2:** Successfully retrieve transcripts for 95%+ of videos with available captions/subtitles

**NFR3:** Returned transcripts must be complete and properly formatted with 100% accuracy (no truncation or corruption)

**NFR4:** Service uptime must exceed 99% for local/tunneled access

**NFR5:** Overall error rate must remain below 5% across all requests

**NFR6:** Container memory footprint must not exceed 512MB per instance

**NFR7:** Support at least 2-3 concurrent transcript requests without performance degradation

**NFR8:** All requests must use OAuth 2.0 bearer token authentication to prevent unauthorized access

**NFR9:** All remote access must use HTTPS (provided by tunnel solution)

**NFR10:** No persistent storage of transcripts or personally identifiable information (PII)

**NFR11:** Comply with YouTube Terms of Service for transcript extraction (personal use, official methods only)

**NFR12:** Stateless service design to enable horizontal scaling if needed

**NFR13:** OAuth credentials and tokens must be securely stored, never logged, and excluded from error messages

**NFR14:** OAuth token validation must complete in <500ms to avoid impacting overall response time

---
