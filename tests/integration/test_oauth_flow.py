import time
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.config import get_config
from src.middleware.oauth import OAuthMiddleware
from src.models.mcp import ToolExecutionContext
from src.registry.tool_registry import ToolRegistry

# Import the actual route handlers and lifespan function
from src.server import health, invoke_tool, lifespan, list_tools

# This file is now active. The global skip has been removed.


@pytest.fixture
def isolated_mcp_app_client(monkeypatch):
    """
    Creates a completely isolated FastAPI app instance for integration testing,
    bypassing any session-wide fixtures from conftest.py.
    """
    # Clear any cached config and set specific env vars for this test client
    get_config.cache_clear()
    monkeypatch.setenv("OAUTH_PROVIDER_URL", "https://test.oauth.provider")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("OAUTH_SCOPES", "read:transcripts")
    monkeypatch.setenv("OAUTH_VALIDATION_ENDPOINT", "https://test.oauth.provider/validate")
    monkeypatch.setenv("OAUTH_TOKEN_CACHE_TTL", "60")

    # Create a fresh app instance and add routes and middleware manually
    app = FastAPI(lifespan=lifespan)
    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/tools/invoke", invoke_tool, methods=["POST"])
    app.add_api_route("/tools/list", list_tools, methods=["GET"])
    app.add_middleware(OAuthMiddleware, exclude_paths=["/health"])

    # Mock the httpx.AsyncClient that the middleware will use
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    # The __aenter__ is used in 'async with' context manager
    mock_client.__aenter__.return_value = mock_client
    monkeypatch.setattr("httpx.AsyncClient", lambda: mock_client)

    with TestClient(app) as client:
        # Yield the client and the mock so tests can configure it
        yield client, mock_client

    get_config.cache_clear()


def test_end_to_end_authenticated_tool_invocation(isolated_mcp_app_client, monkeypatch):
    """
    Test that a tool invocation with a valid OAuth token succeeds and AuthContext is populated.
    """
    client, mock_httpx = isolated_mcp_app_client

    mock_httpx.post.return_value = httpx.Response(
        200,
        json={
            "active": True,
            "scope": "read:transcripts",
            "client_id": "test-client-e2e",
            "exp": int(time.time() + 3600),
        },
        request=httpx.Request("POST", str(get_config().oauth_config.validation_endpoint)),
    )

    # Mock the tool's handler to prevent actual external calls and to inspect the context
    mock_tool_handler = AsyncMock(return_value={"full_text": "mock transcript"})
    registry = ToolRegistry()
    youtube_tool = registry.get_tool("get_youtube_transcript")
    monkeypatch.setattr(youtube_tool, "handler", mock_tool_handler)

    headers = {"Authorization": "Bearer valid_token_for_e2e"}
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": "https://www.youtube.com/watch?v=test"},
    }

    response = client.post("/tools/invoke", headers=headers, json=payload)

    assert response.status_code == 200
    assert response.json()["result"] == {"full_text": "mock transcript"}
    mock_tool_handler.assert_awaited_once()

    # Inspect the context passed to the handler
    args, _ = mock_tool_handler.call_args
    context: ToolExecutionContext = args[1]
    assert context.auth_context is not None
    assert context.auth_context.is_valid is True
    assert context.auth_context.client_id == "test-client-e2e"


def test_end_to_end_unauthenticated_request(isolated_mcp_app_client):
    """
    Test that a tool invocation without an OAuth token is rejected with 401.
    """
    client, _ = isolated_mcp_app_client
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": "https://www.youtube.com/watch?v=test"},
    }

    response = client.post("/tools/invoke", json=payload)

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_request"
    assert "Authorization header is missing" in response.json()["error_description"]


def test_end_to_end_invalid_token_rejection(isolated_mcp_app_client):
    """
    Test that a tool invocation with an invalid OAuth token is rejected with 401.
    """
    client, mock_httpx = isolated_mcp_app_client

    mock_response = httpx.Response(
        401,
        json={"error": "invalid_token", "error_description": "Token is not good"},
        request=httpx.Request("POST", str(get_config().oauth_config.validation_endpoint)),
    )
    mock_httpx.post.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=mock_response.request, response=mock_response
    )

    headers = {"Authorization": "Bearer some_bad_token"}
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": "https://www.youtube.com/watch?v=test"},
    }

    response = client.post("/tools/invoke", headers=headers, json=payload)

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_token", "error_description": "Token is not good"}
