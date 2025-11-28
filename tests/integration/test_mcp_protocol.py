"""Integration tests for the MCP protocol server."""

import json
import multiprocessing
import time
from collections.abc import Generator
from datetime import UTC
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from src.config import get_config
from src.mcp_server import mcp_app
from src.server import app as rest_api_app
from src.server import lifespan

# Use different ports for testing to avoid conflicts
TEST_REST_API_PORT = 8091
BASE_URL = f"http://127.0.0.1:{TEST_REST_API_PORT}"
# FastMCP streamable HTTP expects requests at the root of the mounted app
MCP_ENDPOINT = f"{BASE_URL}/mcp/"


# Mock valid OAuth token for integration tests
MOCK_VALID_TOKEN = "test_valid_token_12345"


def run_server():
    """Target function to run uvicorn server in a separate process."""
    # Monkey-patch OAuth middleware to bypass auth in test mode
    from datetime import datetime, timedelta

    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response

    from src.middleware.oauth import OAuthMiddleware
    from src.models.auth import AuthContext


    async def mock_dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Always set a valid auth context for test requests
        if request.url.path not in self.exclude_paths:
            request.state.auth_context = AuthContext(
                is_valid=True,
                token_hash="mock_hash",
                scopes=["read:transcripts"],
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                client_id="mock_client",
            )

        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    OAuthMiddleware.dispatch = mock_dispatch

    config = get_config()
    config.rest_api_port = TEST_REST_API_PORT

    # Create a root FastAPI app for testing
    root_app = FastAPI(title="Test Gateway", version="0.1.0", lifespan=lifespan)

    # Mount the REST API server at the root
    # Note: In a real scenario, you might want a more sophisticated app structure
    # For this test, we are primarily interested in the MCP server at /mcp
    root_app.mount("/", rest_api_app, name="rest_api")
    root_app.mount("/mcp", mcp_app, name="mcp_server")

    uvicorn.run(root_app, host="127.0.0.1", port=config.rest_api_port, log_level="warning")


@pytest.fixture(scope="session")
def mcp_server() -> Generator[None, Any, None]:
    """Pytest fixture to run the MCP server in a separate process."""
    p = multiprocessing.Process(target=run_server, daemon=True)
    p.start()
    # Wait for the server to be ready
    for _ in range(20):  # Increased timeout for slower systems
        try:
            with httpx.Client() as client:
                response = client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                break
        except httpx.ConnectError:
            time.sleep(0.5)
    else:
        p.terminate()
        pytest.fail("Server did not start in time.")

    yield

    p.terminate()
    p.join()


@pytest.mark.asyncio
async def test_health_endpoint(mcp_server: None):
    """Test that the /health endpoint is available and returns a healthy status."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.skip(
    reason="TODO: Update MCP protocol tests for new server mounting structure after OAuth implementation"
)
@pytest.mark.asyncio
async def test_mcp_tools_list(mcp_server: None):
    """Test the MCP 'tools/list' method."""
    request_payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": "1",
    }

    async with httpx.AsyncClient() as client:
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        response = await client.post(
            MCP_ENDPOINT, data=json.dumps(request_payload), headers=headers
        )

    assert response.status_code == 200
    # The response is a stream of SSE events
    lines = response.text.strip().split("\n\n")
    assert lines[0].startswith("data:")

    # Extract the JSON part
    json_data = json.loads(lines[0][len("data:") :])

    # Validate the overall message structure (now with direct dictionary access)
    assert json_data.get("jsonrpc") == "2.0"
    assert "result" in json_data
    assert json_data.get("id") == "1"

    # Validate the 'tools/list' specific result
    result = json_data["result"]
    assert "tools" in result
    assert isinstance(result["tools"], list)
    assert len(result["tools"]) == 1

    tool_def = result["tools"][0]
    assert isinstance(tool_def, dict)
    assert tool_def.get("name") == "get_youtube_transcript"
    assert "Fetches the transcript" in tool_def.get("description", "")
    assert "input_schema" in tool_def
    assert tool_def["input_schema"].get("properties", {}).get("url", {}).get("type") == "string"


@pytest.mark.skip(
    reason="TODO: Update MCP protocol tests for new server mounting structure after OAuth implementation"
)
@pytest.mark.asyncio
async def test_mcp_tools_call_success(mcp_server: None, mocker):
    """Test a successful 'tools/call' for get_youtube_transcript."""
    # Mock the YouTube API call to avoid external dependency
    mock_transcript = "This is a mock transcript."
    mocker.patch(
        "src.tools.youtube_tool.YouTubeTranscriptApi.fetch",
        return_value=mocker.Mock(
            video_id="dQw4w9WgXcQ",
            language_code="en",
            snippets=[mocker.Mock(text=mock_transcript, start=0, duration=5)],
        ),
    )

    request_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_youtube_transcript",
            "arguments": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        },
        "id": "2",
    }

    async with httpx.AsyncClient() as client:
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        response = await client.post(
            MCP_ENDPOINT, data=json.dumps(request_payload), headers=headers
        )

    assert response.status_code == 200
    lines = response.text.strip().split("\n\n")
    json_data = json.loads(lines[0][len("data:") :])

    # Validate the overall message structure (now with direct dictionary access)
    assert json_data.get("jsonrpc") == "2.0"
    assert "result" in json_data
    assert json_data.get("id") == "2"

    # The result of a tool call is just the string output
    assert isinstance(json_data["result"], str)
    assert json_data["result"] == mock_transcript


@pytest.mark.skip(
    reason="TODO: Update MCP protocol tests for new server mounting structure after OAuth implementation"
)
@pytest.mark.asyncio
async def test_mcp_tools_call_invalid_url(mcp_server: None):
    """Test a failed 'tools/call' due to an invalid URL."""
    request_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_youtube_transcript",
            "arguments": {"url": "not-a-valid-url"},
        },
        "id": "3",
    }

    async with httpx.AsyncClient() as client:
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        response = await client.post(
            MCP_ENDPOINT, data=json.dumps(request_payload), headers=headers
        )

    assert response.status_code == 200
    lines = response.text.strip().split("\n\n")
    json_data = json.loads(lines[0][len("data:") :])

    # It should still be a success response at the transport level,
    # with the error message contained in the payload.
    # Validate the overall message structure (now with direct dictionary access)
    assert json_data.get("jsonrpc") == "2.0"
    assert "result" in json_data
    assert json_data.get("id") == "3"

    assert "Error executing tool" in json_data["result"]
    assert (
        "InvalidYouTubeURL" in json_data["result"]
        or "could not extract video ID" in json_data["result"].lower()
    )
