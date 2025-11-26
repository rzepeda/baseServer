# Bugs and Issues

## Previous Issue: ClosedResourceError
this is the server reported error when connecting
{"event": "Terminating session: None"}
{"event": "Error in message router", "exc_info": ["<class 'anyio.ClosedResourceError'>", "ClosedResourceError()", "<traceback object at 0x74b4ce061cc0>"]}

what is the cause?

---

## Story 1.6: Cloudflare Tunnel Not Routing Requests

**Date:** 2025-11-26
**Status:** DIAGNOSED - Root Cause Identified
**Severity:** Critical

### Summary
Minimal MCP server works perfectly locally but Cloudflare tunnel returns 404 for all endpoints.

### Test Results

#### Local Server (`http://localhost:8080`)
- ✅ `/health` → 200 OK with JSON response
- ✅ `/sse` → 200 OK with SSE stream and session_id
- ✅ `/messages` → 202 Accepted (correct SSE behavior)
- ✅ Server logs show all requests being processed

#### Through Cloudflare Tunnel (`https://grocery-inputs-connectivity-allowed.trycloudflare.com`)
- ❌ `/health` → 404 Not Found (from Cloudflare)
- ❌ `/sse` → 404 Not Found (from Cloudflare)
- ⚠️ Server logs show health requests ARRIVING but responses not returning

### Root Cause
**Cloudflare tunnel is not properly routing requests to/from the local server.**

Requests sometimes reach the server (logs confirm), but responses don't make it back through the tunnel. Other times, Cloudflare returns 404 directly without forwarding the request at all.

### Evidence
1. Tunnel URL: `https://grocery-inputs-connectivity-allowed.trycloudflare.com`
2. Local server running on port 8080: ✅ Confirmed
3. cloudflared process running: ✅ Confirmed
4. Tunnel command: `cloudflared tunnel --url http://localhost:8080`
5. Tunnel log shows "Registered tunnel connection" ✅

### Reproduction Steps
1. Start server: `python -m src` (with `USE_MINIMAL_SERVER=true`)
2. Start tunnel: `cloudflared tunnel --url http://localhost:8080`
3. Test locally: `python test_mcp_endpoints.py http://localhost:8080` → ✅ PASSES
4. Test through tunnel: `python test_mcp_endpoints.py https://grocery-inputs-connectivity-allowed.trycloudflare.com` → ❌ FAILS

### Related Files
- `/mnt/MCPProyects/baseServer/test_mcp_endpoints.py` - Automated test script
- `/mnt/MCPProyects/baseServer/src/minimal_mcp_server.py` - Working server implementation
- `/tmp/cloudflared_new.log` - Tunnel logs

### Impact
- **Story 1.6** blocked on tunnel routing issue
- **Claude.ai integration** not possible until tunnel works