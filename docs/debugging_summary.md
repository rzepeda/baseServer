# MCP Server Connection Debugging Summary

## 1. Objective
The primary goal is to successfully connect a self-hosted Python MCP server to the Claude.ai web client for tool use, secured by OAuth 2.0 using a Keycloak provider. The desired authentication flow is a direct, machine-to-machine connection (Client Credentials) without user-interactive login/redirect.

## 2. Initial State & Architecture
- **Application:** A Python application with a dual-server architecture.
  - **MCP Server (Port 8080):** A specialized server using the `FastMCP` library to handle the `/mcp` protocol path.
  - **REST API Server (Port 8081):** A standard `FastAPI` server for health checks and other RESTful interactions.
- **Infrastructure:** The public URL (`https://agentictools.uk`) was tunneled exclusively to the MCP server on port `8080`.
- **Authentication Logic:** The server was configured to validate bearer tokens against a pre-configured introspection endpoint (`OAUTH_VALIDATION_ENDPOINT` in `.env`), assuming a simple 2-legged OAuth flow.

## 3. Debugging Chronology & Key Findings

A client-side test script, `tests/claude_connector_emulator.py`, was developed to simulate the Claude client and diagnose the connection. The debugging process revealed a series of cascading issues:

1.  **Architectural Mismatch:** The emulator immediately proved that the dual-server architecture was incompatible with the single-port tunnel. The REST API on port `8081` (which initially served health and discovery endpoints) was completely inaccessible from the public internet.
    -   **Fix:** The application was refactored into a **single, unified FastAPI server** running on port 8080. The specialized `FastMCP` application was mounted at the `/mcp` path, and all other endpoints (`/health`, `/tools/list`, discovery) were consolidated onto this main server.

2.  **Incorrect Discovery Protocol:** It was discovered that the Claude client does not use a pre-configured provider URL. It expects to discover the authentication provider from the tool server itself.
    -   **Finding 1:** The user observed Claude attempting to access a `/.well-known/oauth-authorization-server` path.
    -   **Finding 2:** A provided technical document suggested that to force the desired machine-to-machine `client_credentials` flow, the server's discovery response must **omit** the `authorization_endpoint` and explicitly list `client_credentials` as a supported grant type.
    -   **Fix:** A discovery endpoint was added at `/.well-known/oauth-authorization-server`. The response from this endpoint was specifically crafted to meet these requirements, fetching metadata from the Keycloak provider and serving a modified version to the client.

3.  **Missing Registration Endpoint:** A video transcript provided by the user showed a `/register` endpoint being called by the MCP Inspector tool as part of the connection handshake.
    -   **Hypothesis:** The real Claude client might also require this endpoint.
    -   **Fix:** A placeholder `/register` endpoint was added to the server to return a successful acknowledgment, ensuring compatibility with clients that expect it.

4.  **Infrastructure Block:** Throughout the process, the emulator was instrumental in identifying that the external infrastructure (Cloudflare) was blocking requests to the `.well-known` paths with a `401 Unauthorized` error.
    -   **Fix:** The user adjusted their infrastructure configuration, which was confirmed when the emulator successfully accessed the discovery endpoint.

## 4. Current System State

- **Server:** The application is a single, unified FastAPI server. It correctly serves a spec-compliant discovery document at `/.well-known/oauth-authorization-server` designed to force a machine-to-machine flow. It also has the required `/health` and `/register` endpoints.
- **Emulator:** The test script `tests/claude_connector_emulator.py` is also spec-compliant. It successfully performs discovery, obtains a token using client credentials, and accesses a protected endpoint (`/tools/list`), confirming the server and its local configuration are working perfectly.
- **The Problem:** The user reports that the **real Claude client connection still fails.** The last observation was that it was attempting to redirect the user to the auth server, which is the behavior we specifically tried to prevent.

## 5. Recommendation for Next Debugger

The core of the problem lies in a discrepancy between our server's configuration and the Claude client's behavior. We have configured the server to signal for a `client_credentials` flow, but the real client appears to insist on an `authorization_code` (redirect) flow.

1.  **Verify the Claude UI Configuration:** Double-check the fields available in the Claude "Add Server" UI. The presence or absence of a "Token URL" field is critical. If it's present, the `client_credentials` flow should be possible.
2.  **Inspect the Live Handshake:** The final source of truth is the network traffic from the real Claude client. The `Claude-User` agent was seen in the Cloudflare logs. A tool like `mitmproxy` or detailed browser network inspection (if the handshake happens client-side) must be used to capture the exact, step-by-step exchange between the Claude UI/backend and your server when you click "Connect".
3.  **Analyze the Captured Traffic:** The captured traffic will unambiguously show:
    -   Which discovery endpoint Claude actually calls first.
    -   What response it receives.
    -   Whether it proceeds to the `token_endpoint` or the `authorization_endpoint`.
    -   The exact payload of the request that is failing.

The codebase has been refactored to be correct based on all information gathered so far. The final issue can only be diagnosed by observing the live traffic from the real client.
