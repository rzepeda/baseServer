from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from starlette.testclient import TestClient
from fastapi import FastAPI

from src.config import get_config
from src.middleware.oauth import OAuthMiddleware
from src.models.mcp import ToolExecutionContext
from src.registry.tool_registry import ToolRegistry
from src.server import lifespan, invoke_tool, list_tools, health
from tests.unit.test_oauth_middleware import create_test_jwt, jwks_keys


@pytest.fixture
def isolated_mcp_app_client(monkeypatch, jwks_keys):
    """
    Creates a completely isolated FastAPI app instance for integration testing.
    This fixture patches the config and JWKS fetching to test the full flow.
    """
    # Clear any cached config
    get_config.cache_clear()
    
    # Mock config
    mock_cfg = MagicMock()
    mock_cfg.keycloak_url = "https://test.keycloak.com"
    mock_cfg.keycloak_realm = "test-realm"
    mock_cfg.oauth_token_cache_ttl = 0  # Disable caching
    
    private_key, public_key = jwks_keys

    with patch('src.middleware.oauth.get_config', return_value=mock_cfg), \
         patch('src.server.get_config', return_value=mock_cfg), \
         patch('src.middleware.oauth._get_cached_jwks') as mock_get_jwks:
        
        mock_get_jwks.return_value = {"keys": [public_key]}
        
        # Create a fresh app instance
        app = FastAPI(lifespan=lifespan)
        app.add_api_route("/health", health, methods=["GET"])
        app.add_api_route("/tools/invoke", invoke_tool, methods=["POST"])
        app.add_api_route("/tools/list", list_tools, methods=["GET"])
        app.add_middleware(OAuthMiddleware, exclude_paths=["/health"])

        with TestClient(app) as client:
            yield client, private_key, mock_cfg

    # Clear cache again after test
    get_config.cache_clear()


def test_e2e_authenticated_tool_invocation(isolated_mcp_app_client, monkeypatch):
    """
    Tests the full end-to-end flow of invoking a tool with a valid JWT.
    Ensures the AuthContext is correctly passed down to the tool handler.
    """
    client, private_key, mock_config = isolated_mcp_app_client

    # Mock the actual tool handler to prevent external calls and inspect its context
    mock_tool_handler = AsyncMock(return_value={"result": "success"})
    registry = ToolRegistry() # Get singleton instance
    # It's better to patch the method on the instance if possible
    monkeypatch.setattr(registry.get_tool("get_youtube_transcript"), "handler", mock_tool_handler)

    # Create a valid token
    issuer = f"{mock_config.keycloak_url}/realms/{mock_config.keycloak_realm}"
    token = create_test_jwt(private_key, issuer, "account")

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": "https://youtube.com/watch?v=123"},
        "context": {"correlation_id": "test-e2e-123"}
    }
    
    response = client.post("/tools/invoke", headers=headers, json=payload)

    # --- Asserts ---
    assert response.status_code == 200
    assert response.json()["result"] == {"result": "success"}
    
    # Verify the tool handler was called
    mock_tool_handler.assert_awaited_once()

    # Inspect the context passed to the handler
    args, _ = mock_tool_handler.call_args
    exec_context: ToolExecutionContext = args[1]

    assert exec_context is not None
    assert exec_context.auth_context is not None
    assert exec_context.auth_context.is_valid is True
    assert exec_context.auth_context.client_id == "test-client"
    assert exec_context.auth_context.user_id == "test-user-id"
    assert "read:transcripts" in exec_context.auth_context.scopes
    assert exec_context.correlation_id == "test-e2e-123"

def test_e2e_unauthenticated_tool_invocation(isolated_mcp_app_client):
    """
    Tests that invoking a tool without a token is rejected.
    """
    client, _, _ = isolated_mcp_app_client

    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": "https://youtube.com/watch?v=123"},
    }
    
    response = client.post("/tools/invoke", json=payload)

    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_request"
    assert "Authorization header is missing" in data["error_description"]