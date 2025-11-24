# Connecting to Claude.ai

This guide explains how to connect your MCP server to Claude.ai as a Remote MCP Server.

## Connection Details

**Server URL:** `https://thermal-lang-jewish-excitement.trycloudflare.com/mcp`

**Important:** The server uses Anthropic's FastMCP in streamable HTTP mode, which is compatible with Cloudflare tunnel. The MCP endpoint is `/mcp`, not `/sse` or `/messages/`.

## Prerequisites

1. Server must be running locally:
   ```bash
   source .venv/bin/activate
   python -m src
   ```

2. Cloudflare tunnel must be active and pointing to `localhost:8080`

## Steps to Connect in Claude.ai

1. Open Claude.ai in your browser
2. Click on your profile or settings
3. Navigate to "MCP Servers" or "Remote Servers" section
4. Click "Add Remote MCP Server"
5. Enter the following details:
   - **Name:** `YouTube Transcript Server`
   - **URL:** `https://thermal-lang-jewish-excitement.trycloudflare.com/mcp`
   - **Authentication:** None (OAuth deferred to Epic 2)
6. Click "Connect" or "Add Server"
7. Claude.ai will connect to the MCP endpoint and discover available tools

## Available Tools

Once connected, Claude.ai will have access to:

- **get_youtube_transcript**: Fetches transcripts from YouTube videos
  - Input: YouTube video URL (supports youtube.com, youtu.be, m.youtube.com)
  - Output: Full transcript text

## Testing the Connection

You can verify the server is working before connecting Claude.ai:

```bash
# Test tools/list
curl -X POST "https://thermal-lang-jewish-excitement.trycloudflare.com/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test get_youtube_transcript
curl -X POST "https://thermal-lang-jewish-excitement.trycloudflare.com/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc":"2.0",
    "id":2,
    "method":"tools/call",
    "params":{
      "name":"get_youtube_transcript",
      "arguments":{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    }
  }'
```

## Troubleshooting

### Server Not Responding

1. Check if server is running:
   ```bash
   ps aux | grep "python -m src"
   ```

2. Check server logs:
   ```bash
   tail -f server.log
   ```

3. Test health endpoint:
   ```bash
   curl https://thermal-lang-jewish-excitement.trycloudflare.com/health
   ```

### Connection Timeout

- Cloudflare tunnel URL changes each time tunnel restarts
- Update `.env` with new `CLOUDFLARE_TUNNEL_URL` if tunnel restarted
- Verify tunnel is forwarding to correct port (8080)

### Authentication Errors

- Authentication is not yet implemented (Epic 2)
- Claude.ai should connect without credentials
- If prompted for auth, select "No Authentication" or "Skip"

## Architecture Notes

The server uses:
- **FastMCP's streamable HTTP mode** (`stateless_http=True`)
- **Single endpoint at `/mcp`** for all MCP protocol messages
- **Streamable HTTP transport** compatible with Cloudflare tunnel
- **No SSE session required** - each request is stateless but responses stream

This configuration avoids the SSE compatibility issues with Cloudflare's free tunnel service while maintaining protocol compliance.
