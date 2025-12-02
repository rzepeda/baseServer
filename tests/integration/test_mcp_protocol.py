"""Integration tests for the MCP protocol server."""

import json
import multiprocessing
import time
from collections.abc import Generator
from typing import Any
from unittest.mock import patch  # Added patch, MagicMock

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from pydantic import SecretStr  # Added SecretStr

from src.mcp_server import mcp_app
from src.server import app as rest_api_app
from src.server import lifespan
from tests.unit.test_oauth_middleware import create_test_jwt  # Added create_test_jwt

# Use different ports for testing to avoid conflicts
TEST_REST_API_PORT = 8091
BASE_URL = f"http://127.0.0.1:{TEST_REST_API_PORT}"
# FastMCP streamable HTTP expects requests at the root of the mounted app
MCP_ENDPOINT = f"{BASE_URL}/"


def run_server(mock_config_data: dict, jwks_mock_data: dict):
    """Target function to run uvicorn server in a separate process."""
    # Apply patches within the subprocess
    import src.config
    import src.middleware.oauth
    import src.models.auth
    from src.config import Config
    from src.mcp_server import mcp_app # Import the mcp_app directly

    # Clear any cached config in this subprocess before applying patches
    src.config.get_config.cache_clear()

    # Convert SecretStr back from string for Config instantiation
    if 'oauth_client_secret' in mock_config_data:
        mock_config_data['oauth_client_secret'] = SecretStr(mock_config_data['oauth_client_secret'])
    
    real_config_instance = Config(**mock_config_data, _env_file='')

    with (
        patch.object(src.config, 'get_config', return_value=real_config_instance),
        patch.object(src.middleware.oauth, '_get_cached_jwks', return_value=jwks_mock_data)
    ):
        config = src.config.get_config()
        config.rest_api_port = TEST_REST_API_PORT # The port uvicorn will run on
        config.use_oauth = True # Ensure OAuth is active for the test

        # Run only the mcp_app for this protocol test
        uvicorn.run(mcp_app, host="127.0.0.1", port=config.rest_api_port, log_level="warning")


@pytest.fixture(scope="session")
def mock_config_for_mcp_tests() -> dict:
    """Mock config dictionary for the MCP server with OAuth enabled, using user-provided .env values."""
    config_dict = {
        "server_host": "0.0.0.0",
        "mcp_port": 8080,
        "rest_api_port": 8081,
        "cors_allowed_origins": "",
        "log_level": "DEBUG",
        "environment": "development",
        "cloudflare_tunnel_url": "https://frequently-introducing-segment-keep.trycloudflare.com/mcp",
        "use_oauth": True,
        "use_sse": False,
        # User-provided .env values
        "keycloak_url": "https://auth.agentictools.uk",
        "keycloak_realm": "mcpServerAuth",
        "oauth_provider_url": "https://auth.agentictools.uk/realms/mcpServerAuth",
        "oauth_client_id": "mcpServer",
        "oauth_client_secret": "test-secret", # This is a mock secret for testing
        "oauth_scopes": "openid profile email read:transcripts", # Assuming this is the default or required scope
        "oauth_validation_endpoint": "https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token/introspect",
        "oauth_token_cache_ttl": 0,
    }
    return config_dict


@pytest.fixture(scope="session")
def auth_token(jwks_keys, mock_config_for_mcp_tests: dict):
    """Generates a valid JWT token for testing."""
    _, main_private_pem, _, _, _, _ = jwks_keys
    # Use oauth_provider_url directly for the issuer to ensure exact match with middleware's validation
    issuer = mock_config_for_mcp_tests['oauth_provider_url']
    token = create_test_jwt(main_private_pem, issuer, mock_config_for_mcp_tests['oauth_client_id'])
    return token


@pytest.fixture(scope="session")
def mcp_server(mock_config_for_mcp_tests: dict, jwks_keys) -> Generator[None, Any, None]:
    """Pytest fixture to run the MCP server in a separate process."""
    # Configure mock_httpx_get to return the public JWKS keys
    _, _, _, main_public_jwk_dict, _, _ = jwks_keys
    jwks_mock_data = {"keys": [main_public_jwk_dict]}

    # Pass the config data and jwks data to the run_server function
    p = multiprocessing.Process(target=run_server, args=(mock_config_for_mcp_tests, jwks_mock_data), daemon=True)
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


@pytest.mark.asyncio
async def test_mcp_tools_list(mcp_server: None, auth_token: str):
    """Test the MCP 'tools/list' method."""
    request_payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": "1",
    }

    async with httpx.AsyncClient() as client:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {auth_token}",
        }
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


@pytest.mark.asyncio
async def test_mcp_tools_call_success(mcp_server: None, mocker, auth_token: str):
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
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {auth_token}",
        }
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


@pytest.mark.asyncio
async def test_mcp_tools_call_invalid_url(mcp_server: None, auth_token: str):
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
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {auth_token}",
        }
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


@pytest.mark.asyncio
async def test_mcp_unauthorized_access(mcp_server: None):
    """Test that MCP endpoints return 401 Unauthorized without a token."""
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
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "invalid_request"
        assert "Authorization header is missing" in data["error_description"]
