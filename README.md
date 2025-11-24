# YouTube MCP Server

This project is an extensible MCP (Model Context Protocol) server designed to provide tools for interacting with YouTube. It implements the official Anthropic MCP specification, allowing seamless integration with Claude.ai via the "Remote MCP Server" feature.

## Architecture

This project implements a **dual-server architecture**:

1. **MCP Protocol Server (Port 8080)** - For Claude.ai integration
   - Implements Anthropic's MCP specification
   - SSE (Server-Sent Events) transport
   - JSON-RPC 2.0 message format
   - Mounted at `/mcp` endpoint

2. **REST API Server (Port 8081)** - For direct API access
   - Custom REST endpoints
   - Backwards compatibility for curl/scripts
   - Direct tool invocation

Both servers share the same tool implementations (YouTube transcript tool) and tool registry.

## Features

- MCP protocol-compliant server using Anthropic's official `mcp` Python SDK
- Dual-server architecture for both Claude.ai integration and direct API access
- Extensible tool registry for adding new MCP tools
- Health check endpoints on both servers
- Structured JSON logging with correlation IDs
- Configuration driven by environment variables
- Cloudflare Tunnel support for secure remote access

## Setup and Installation

### Prerequisites

- Python 3.12+
- pip
- **Cloudflare Account** (free tier sufficient) - Required for remote access via Cloudflare Tunnel
- **cloudflared CLI** - Cloudflare Tunnel client software

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```
    Alternatively, if you are using a `pyproject.toml` based workflow:
    ```bash
    pip install -e .[dev]
    ```

4.  **Configure environment variables:**
    Create a `.env` file by copying the `.env.example`:
    ```bash
    cp .env.example .env
    ```
    Update the `.env` file with your specific configuration, such as OAuth credentials.

## Running the Servers

The project runs **both servers concurrently** using a single command:

```bash
source .venv/bin/activate && python -m src
```

This starts:
- **MCP Protocol Server** on port `8080` (configurable via `MCP_PORT` env var)
- **REST API Server** on port `8081` (configurable via `REST_API_PORT` env var)

Both servers will be running simultaneously and can be accessed independently.

### Verifying Server Status

Check MCP server health:
```bash
curl http://localhost:8080/health
curl https://thermal-lang-jewish-excitement.trycloudflare.com/health
```

Check REST API server health:
```bash
curl http://localhost:8081/health
```

Expected response from both:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-11-23T...",
  "tools_loaded": 1,
  "registered_tools": ["get_youtube_transcript"]
}
```

## Connecting to Claude.ai

Once your MCP server is running and accessible via Cloudflare Tunnel (see next section), you can integrate it with Claude.ai:

### Step 1: Get Your Cloudflare Tunnel URL

Start the Cloudflare Tunnel (see detailed setup in the next section):

```bash
# Quick tunnel (temporary URL)
cloudflared tunnel --url http://localhost:8080
```

Copy the tunnel URL from the output (e.g., `https://calendar-computational-bring-ever.trycloudflare.com`).

**IMPORTANT:** Update your `.env` file with this URL:
```bash
CLOUDFLARE_TUNNEL_URL=https://thermal-lang-jewish-excitement.trycloudflare.com
```

### Step 2: Configure Remote MCP Server in Claude.ai

1. Open [Claude.ai](https://claude.ai) in your browser
2. Click on your profile icon (bottom-left corner)
3. Select **"Settings"** → **"Integrations"** → **"Remote MCP Servers"**
4. Click **"Add Server"**

### Step 3: Enter Server Configuration

Fill in the following fields:

- **Name:** `YouTube Transcript Server` (or any descriptive name)
- **URL:** Your Cloudflare tunnel URL from Step 1
  - Example: `https://calendar-computational-bring-ever.trycloudflare.com`
  - **Note:** Use the full HTTPS URL without any path (no `/mcp` suffix needed)
- **Authentication:** Leave blank for now (OAuth will be added in Epic 2)

Click **"Connect"** or **"Save"**.

### Step 4: Verify Connection

1. Claude.ai will attempt to connect to your MCP server
2. Look for a **"Connected"** status indicator
3. If connection fails, check:
   - Local servers are running (`python -m src`)
   - Cloudflare tunnel is active
   - Tunnel URL in Claude.ai matches the URL in your `.env` file
   - Firewall/network allows outbound connections

### Step 5: Test the Tool

In a new Claude.ai chat:

```
Can you get me the transcript for this YouTube video?
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Claude should:
1. Recognize the `get_youtube_transcript` tool is available
2. Invoke the tool via MCP protocol
3. Return the video transcript in the response

### Updating Tunnel URL After Restart

**Quick tunnel URLs change on every restart!** After restarting `cloudflared`:

1. Copy the new URL from the `cloudflared` terminal output
2. Update `.env` file:
   ```bash
   CLOUDFLARE_TUNNEL_URL=https://new-subdomain.trycloudflare.com
   ```
3. Update the URL in Claude.ai Remote MCP Server settings
4. Reconnect the server in Claude.ai

**Tip:** Use a named tunnel (see Cloudflare Tunnel section) for a persistent URL that doesn't change.

## Running Tests

To run the test suite, activate the virtual environment and use `pytest`:

```bash
source .venv/bin/activate && pytest
```

For coverage reports:
```bash
source .venv/bin/activate && pytest --cov=src --cov-report=term-missing
```

## Cloudflare Tunnel Setup for Remote Access

Cloudflare Tunnel enables secure remote access to your locally-running **MCP Protocol Server (port 8080)** without exposing ports or configuring firewalls. This allows Claude.ai to connect to your local server remotely.

**Important:** The tunnel must point to **port 8080** (MCP server), not port 8081 (REST API server).

### Prerequisites

1. **Cloudflare Account**: Sign up at [cloudflare.com](https://www.cloudflare.com) (free tier is sufficient)
2. **Domain Name**: Use either:
   - A Cloudflare-provided subdomain (e.g., `*.trycloudflare.com`)
   - Your own custom domain managed through Cloudflare DNS
3. **cloudflared CLI**: Install the Cloudflare Tunnel client

### Installing cloudflared

**Linux:**
```bash
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

**macOS:**
```bash
brew install cloudflare/cloudflare/cloudflared
```

**Windows:**
Download from [GitHub Releases](https://github.com/cloudflare/cloudflared/releases)

### One-Time Tunnel Setup

#### Option 1: Quick Tunnel (Temporary - Easiest for Testing)

For quick testing without DNS configuration:

```bash
# Start local server first
source .venv/bin/activate && python -m src

# In a separate terminal, start a quick tunnel
cloudflared tunnel --url http://localhost:8080
```

This provides a temporary URL (e.g., `https://xyz.trycloudflare.com`) that expires when you stop the tunnel.

#### Option 2: Named Tunnel (Permanent - Recommended for Development)

For persistent tunnel configuration:

1. **Authenticate with Cloudflare:**
   ```bash
   cloudflared tunnel login
   ```
   This opens a browser to authorize your account.

2. **Create a named tunnel:**
   ```bash
   cloudflared tunnel create mcp-server
   ```
   Save the tunnel UUID shown in the output.

3. **Create tunnel configuration:**
   Create a `cloudflare-tunnel.yml` file in the project root (see `cloudflare-tunnel.yml.example` for template):
   ```yaml
   tunnel: <your-tunnel-uuid>
   credentials-file: /home/<user>/.cloudflared/<tunnel-uuid>.json

   ingress:
     - hostname: mcp.yourdomain.com
       service: http://localhost:8080
     - service: http_status:404
   ```

4. **Configure DNS:**
   ```bash
   cloudflared tunnel route dns mcp-server mcp.yourdomain.com
   ```
   This creates a CNAME record pointing to your tunnel.

5. **Verify DNS propagation:**
   ```bash
   nslookup mcp.yourdomain.com
   ```

### Daily Usage Workflow

1. **Start the MCP server:**
   ```bash
   source .venv/bin/activate && python -m src
   ```
   The server will start on `localhost:8080`.

2. **Start the Cloudflare Tunnel** (in a separate terminal):

   **Quick Tunnel:**
   ```bash
   cloudflared tunnel --url http://localhost:8080
   ```

   **Named Tunnel:**
   ```bash
   cloudflared tunnel run mcp-server
   ```

3. **Verify connectivity:**
   Test the health endpoint from any network:
   ```bash
   curl https://your-tunnel-url/health
   ```
   Expected response: `{"status": "healthy"}`

4. **Use the tool remotely:**
   ```bash
   curl -X POST "https://your-tunnel-url/tools/invoke" \
     -H "Content-Type: application/json" \
     -d '{
       "tool_name": "get_youtube_transcript",
       "parameters": {
         "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
       }
     }'
   ```

5. **Stop when finished:**
   - Stop tunnel: `Ctrl+C` in tunnel terminal
   - Stop server: `Ctrl+C` in server terminal

### Checking Tunnel Status

**View tunnel logs:**
```bash
cloudflared tunnel run mcp-server
```
Look for "Connection established" messages.

**List all tunnels:**
```bash
cloudflared tunnel list
```

**Check tunnel info:**
```bash
cloudflared tunnel info mcp-server
```

### Troubleshooting

#### Tunnel Connection Failures

**Problem:** Tunnel fails to connect
- **Solution:** Ensure local server is running on port 8080 first
- **Check:** Run `curl http://localhost:8080/health` to verify local server

**Problem:** "tunnel credentials not found"
- **Solution:** Verify credentials file path in `cloudflare-tunnel.yml`
- **Check:** Credentials should be in `~/.cloudflared/<tunnel-uuid>.json`

#### DNS Issues

**Problem:** DNS not resolving
- **Solution:** Wait 1-5 minutes for DNS propagation
- **Check:** Use `nslookup` or `dig` to verify CNAME record

**Problem:** CNAME record not created
- **Solution:** Run `cloudflared tunnel route dns <tunnel-name> <hostname>` again
- **Check:** Verify in Cloudflare DNS dashboard

#### Port Conflicts

**Problem:** "address already in use" error
- **Solution:** Check if another process is using port 8080
- **Check:** Run `lsof -i :8080` (Linux/macOS) or `netstat -ano | findstr :8080` (Windows)

#### Certificate Errors

**Problem:** Browser shows certificate warnings
- **Solution:** Cloudflare-managed certificates are automatic; this rarely happens
- **Check:** Ensure using `https://` not `http://` in URL

### Security Considerations

**⚠️ IMPORTANT SECURITY NOTICE:**

- **No Authentication Yet:** OAuth 2.0 authentication will be added in Epic 2 (Story 2.1)
- **Keep URL Private:** Do not share your tunnel URL publicly until authentication is implemented
- **HTTPS Only:** Always use HTTPS URLs (Cloudflare provides automatic TLS)
- **Free Tier:** Cloudflare free tier includes DDoS protection and automatic HTTPS certificates

### Known Limitations

1. **No OAuth Protection:** Authentication will be added in Epic 2, Story 2.1
2. **Local Machine Dependency:** Tunnel only works when your local machine is running and online
3. **Single Point of Failure:** If local machine goes offline, the tunnel becomes unavailable
4. **Development Only:** This setup is for local development; production deployment will use Kubernetes (Epic 2)
5. **Temporary URLs (Quick Tunnel):** Quick tunnel URLs expire when the tunnel stops; use named tunnels for persistence

### MCP Protocol Connection Troubleshooting

#### Problem: Claude.ai shows "Connection Failed" or "Disconnected"

**Possible Causes & Solutions:**

1. **Stale Tunnel URL** (Most Common)
   - **Cause:** Quick tunnel URLs change on every `cloudflared` restart
   - **Solution:**
     ```bash
     # Get the current tunnel URL from cloudflared output
     # Update .env file
     CLOUDFLARE_TUNNEL_URL=https://new-subdomain.trycloudflare.com
     # Update URL in Claude.ai Remote MCP Server settings
     # Reconnect the server
     ```

2. **MCP Server Not Running**
   - **Check:** `curl http://localhost:8080/health`
   - **Solution:** Run `python -m src` in the project directory

3. **Cloudflare Tunnel Not Running**
   - **Check:** Look for "Connection established" in `cloudflared` terminal
   - **Solution:** Restart tunnel: `cloudflared tunnel --url http://localhost:8080`

4. **Wrong Port in Tunnel Configuration**
   - **Check:** Tunnel must point to `localhost:8080` (MCP server)
   - **Not:** `localhost:8081` (REST API server)

#### Problem: SSE Connection Failures

**Symptoms:** Claude.ai connects but tools don't work

**Solutions:**
1. Verify MCP server SSE endpoint is accessible:
   ```bash
   curl -N -H "Accept: text/event-stream" https://your-tunnel-url/mcp
   ```
2. Check server logs for SSE connection errors
3. Ensure no proxy/CDN is buffering SSE responses

#### Problem: JSON-RPC Error Messages in Claude.ai

**Symptoms:** Tool invocations fail with "RPC error" messages

**Solutions:**
1. Check server logs for detailed error messages
2. Verify tool is registered: `curl http://localhost:8080/health`
3. Test tool directly via REST API (port 8081):
   ```bash
   curl -X POST http://localhost:8081/tools/invoke \
     -H "Content-Type: application/json" \
     -d '{"tool_name": "get_youtube_transcript", "parameters": {"url": "https://youtube.com/watch?v=..."}}'
   ```

#### Problem: Protocol Version Mismatch

**Symptoms:** "Unsupported protocol version" errors

**Solutions:**
1. Update MCP SDK: `pip install --upgrade mcp`
2. Verify SDK version: `pip show mcp`
3. Check MCP SDK is >= 0.1.0

#### Problem: Timeout Issues

**Symptoms:** Connections timeout or tools take too long

**Solutions:**
1. Check network latency to Cloudflare edge
2. Test local tool execution speed (should be <5 seconds)
3. Increase timeout in Claude.ai settings if available
4. Check YouTube API is accessible from your network

#### Debugging Checklist

When troubleshooting MCP connection issues, verify:

- [ ] Local servers running: `python -m src`
- [ ] MCP server health: `curl http://localhost:8080/health`
- [ ] Cloudflare tunnel active and showing "Connection established"
- [ ] Tunnel URL matches between `cloudflared` output, `.env` file, and Claude.ai settings
- [ ] Tunnel points to port 8080 (not 8081)
- [ ] No firewall blocking outbound connections
- [ ] MCP SDK installed: `pip show mcp`
- [ ] Server logs show no errors: Check terminal running `python -m src`

### Additional Resources

- [Anthropic MCP Documentation](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/anthropics/mcp-python-sdk)
- [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [cloudflared CLI Reference](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/)
- [Troubleshooting Guide](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/troubleshooting/)
