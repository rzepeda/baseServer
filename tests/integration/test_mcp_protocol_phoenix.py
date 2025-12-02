"""Integration tests for the MCP protocol server using FastAPI TestClient."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from authlib.jose.rfc7517.jwk import JsonWebKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from pydantic import SecretStr
from starlette.routing import Route
from starlette.responses import JSONResponse

from src.config import Config
from src.middleware.oauth import OAuthMiddleware
from src.models.auth import AuthContext
from src.registry.tool_registry import ToolRegistry
from src.utils.context import auth_context_var
from src.mcp_server import get_youtube_transcript # Assuming tool is defined and needs to be registered
from src.tools.youtube_tool import YouTubeTool
from src.tools.hello_world_tool import HelloWorldTool


# --- Test Configuration and Fixtures ---

@pytest.fixture(scope="session")
def mock_config_for_mcp_tests_phoenix() -> Config:
    """Mock config for the MCP server with OAuth enabled for TestClient."""
    get_config_mock = MagicMock(spec=Config)
    get_config_mock.server_host = "0.0.0.0"
    get_config_mock.mcp_port = 8090
    get_config_mock.rest_api_port = 8091
    get_config_mock.cors_allowed_origins = ""
    get_config_mock.log_level = "DEBUG"
    get_config_mock.environment = "development"
    get_config_mock.cloudflare_tunnel_url = "https://frequently-introducing-segment-keep.trycloudflare.com/mcp"
    get_config_mock.use_oauth = True
    get_config_mock.use_sse = False # Use streamable_http_app
    get_config_mock.keycloak_url = "https://auth.agentictools.uk"
    get_config_mock.keycloak_realm = "mcpServerAuth"
    get_config_mock.oauth_provider_url = "https://auth.agentictools.uk/realms/mcpServerAuth"
    get_config_mock.oauth_client_id = "mcpServer"
    get_config_mock.oauth_client_secret = SecretStr("test-secret")
    get_config_mock.oauth_scopes = "openid profile email read:transcripts"
    get_config_mock.oauth_validation_endpoint = "https://auth.agentictools.uk/realms/mcpServerAuth/protocol/openid-connect/token/introspect"
    get_config_mock.oauth_token_cache_ttl = 0
    return get_config_mock


@pytest.fixture(scope="session")
def jwks_keys_phoenix():
    """Generates a consistent set of RSA keys for JWT signing and validation."""
    main_private_key_crypto = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    main_private_pem = main_private_key_crypto.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    main_public_key_crypto = main_private_key_crypto.public_key()
    main_public_pem = main_public_key_crypto.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    main_public_jwk_dict = JsonWebKey.import_key(main_public_pem).as_dict()
    # --- Explicitly set a KID to ensure consistency ---
    custom_kid = "test-key-id-phoenix"
    main_public_jwk_dict["kid"] = custom_kid
    main_public_jwk_dict["alg"] = "RS256"

    # Save the public JWK to a temporary file for the middleware to read
    import tempfile
    import json
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as f:
        json.dump({"keys": [main_public_jwk_dict]}, f)
        public_jwk_file_path = f.name
    
    yield main_private_pem, main_public_jwk_dict, public_jwk_file_path
    
    # Clean up the temporary file after the session
    import os
    os.unlink(public_jwk_file_path)


def create_test_jwt_phoenix(
    private_key_pem: str,
    issuer: str,
    client_id: str,
    kid: str,  # Make kid a required argument
    claims_override: dict | None = None,
) -> str:
    """Helper to create a signed JWT for testing."""
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=5)
    iat = now
    jti = "test-jti"

    default_claims = {
        "iss": issuer,
        "aud": "account",
        "exp": exp,
        "iat": iat,
        "jti": jti,
        "client_id": client_id,
        "sub": "test-user-id",
        "preferred_username": "test-user",
        "scope": "openid profile email read:transcripts",
        "azp": client_id,
        "typ": "Bearer",
    }

    if claims_override:
        default_claims.update(claims_override)
    
    # Use the explicitly provided kid
    headers = {"kid": kid, "alg": "RS256", "typ": "JWT"}

    return jose_jwt.encode(default_claims, private_key_pem, algorithm="RS256", headers=headers)


@pytest.fixture(scope="session")
def auth_token_phoenix(
    jwks_keys_phoenix, mock_config_for_mcp_tests_phoenix: Config
) -> str:
    """Generates a valid JWT token for testing."""
    private_pem, public_jwk_dict, _ = jwks_keys_phoenix # Unpack the file path, but we don't need it here
    issuer = mock_config_for_mcp_tests_phoenix.oauth_provider_url
    token = create_test_jwt_phoenix(
        private_pem,
        issuer,
        mock_config_for_mcp_tests_phoenix.oauth_client_id,
        kid=public_jwk_dict["kid"],  # Use the explicitly set kid
    )
    return token


@pytest.fixture(scope="function") # Changed scope to function
def mcp_test_client_phoenix(
    mock_config_for_mcp_tests_phoenix: Config, jwks_keys_phoenix, monkeypatch
) -> TestClient:
    """Fixture to create a TestClient for the MCP application."""
    private_pem, public_jwk_dict, public_jwk_file_path = jwks_keys_phoenix
    # jwks_mock_data = {"keys": [public_jwk_dict]} # This is technically not used anymore

    # Set the environment variable for _get_cached_jwks to read the JWKS file
    monkeypatch.setenv("PYTEST_JWKS_FILE_PATH", public_jwk_file_path)
    # Ensure PYTEST_CURRENT_TEST is set for the middleware's conditional logic
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "true")

    # Mock the get_config to return our test configuration
    with patch("src.config.get_config", return_value=mock_config_for_mcp_tests_phoenix):
        
        # Manually initialize ToolRegistry for the host_app's state
        registry = ToolRegistry()
        registry._registered_tools = {} # Clear for clean state
        registry._registered_metadata = {}
        # Tools are now registered via @_mcp_instance.tool(), so manual registration is not needed here.
        # registry.register_tool(YouTubeTool())
        # registry.register_tool(HelloWorldTool())

        # Initialize FastMCP application directly
        _mcp_instance = FastMCP(
            "youtube-transcript-server",
            stateless_http=not mock_config_for_mcp_tests_phoenix.use_sse,
        )

        # Define the tool directly on the FastMCP instance for this test
        @_mcp_instance.tool()
        async def get_youtube_transcript(url: str) -> str:
            """Fetches the transcript for a given YouTube video URL."""
            # For this test, we just need to ensure the tool is callable.
            # We can mock its internal logic in the specific test.
            return "Transcript for " + url
        
        # Export the proper ASGI app based on configuration
        if mock_config_for_mcp_tests_phoenix.use_sse:
            mcp_asgi_app = _mcp_instance.sse_app()
        else:
            mcp_asgi_app = _mcp_instance.streamable_http_app()
        
        # DEBUG: Print routes of the raw FastMCP app
        print(f"DEBUG: mcp_asgi_app (Streamable HTTP) routes: {mcp_asgi_app.routes}\n")

        # Add the health check endpoint for TestClient
        async def health_check_route(request):
            return JSONResponse({"status": "healthy"})
        mcp_asgi_app.router.routes.append(Route("/health", health_check_route))

        # Apply OAuthMiddleware directly to mcp_asgi_app
        mcp_asgi_app_with_middleware = OAuthMiddleware(mcp_asgi_app, exclude_paths=["/health"])

        # Create a FastAPI app to host the mcp_asgi_app and apply middleware
        host_app = FastAPI()
        host_app.mount("/", mcp_asgi_app_with_middleware) # Mount the middleware-wrapped app at the root

        # IMPORTANT: Manually set the tool registry on the app state for tests
        host_app.state.registry = registry # Assign to the wrapped app
        
        return TestClient(host_app) # Use the host_app (with middleware) for the client


# --- Tests ---

@pytest.mark.asyncio
async def test_phoenix_health_endpoint_unauthenticated(mcp_test_client_phoenix: TestClient):
    """Test that the /health endpoint is available and returns a healthy status."""
    response = mcp_test_client_phoenix.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_phoenix_mcp_tools_list_authenticated(
    mcp_test_client_phoenix: TestClient,
    auth_token_phoenix: str,
):
    """Test the MCP 'tools/list' method with authentication."""
    request_payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": "1",
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token_phoenix}",
    }
    response = mcp_test_client_phoenix.post("/v1/tools", data=json.dumps(request_payload), headers=headers)

    assert response.status_code == 200
    lines = response.text.strip().split("\n\n")
    assert lines[0].startswith("data:")

    json_data = json.loads(lines[0][len("data:") :])

    assert json_data.get("jsonrpc") == "2.0"
    assert "result" in json_data
    assert json_data.get("id") == "1"

    result = json_data["result"]
    assert "tools" in result
    assert isinstance(result["tools"], list)
    assert len(result["tools"]) >= 1 # At least one tool should be registered

    tool_def = result["tools"][0]
    assert isinstance(tool_def, dict)
    assert tool_def.get("name") == "get_youtube_transcript"
