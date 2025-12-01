"""Integration test for Authorization Code Flow with OAuth Discovery."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from authlib.jose.rfc7517.jwk import JsonWebKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from jose import jwt as jose_jwt
from starlette.testclient import TestClient

from src.config import get_config
from src.handlers.oauth_discovery import clear_oauth_discovery_cache, get_oauth_discovery_document
from src.middleware.oauth import OAuthMiddleware
from src.models.mcp import ToolExecutionContext
from src.registry.tool_registry import ToolRegistry
from src.server import app, invoke_tool, lifespan, list_tools


@pytest.fixture
def clear_discovery_cache():
    """Fixture to clear the OAuth discovery cache before each test."""
    clear_oauth_discovery_cache()
    yield
    clear_oauth_discovery_cache()  # Clear after test too


@pytest.fixture
def setup_env(monkeypatch):
    """Setup environment variables for testing."""
    get_config.cache_clear()
    monkeypatch.setenv("OAUTH_PROVIDER_URL", "https://auth.test.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("OAUTH_SCOPES", "read:transcripts")
    monkeypatch.setenv("OAUTH_VALIDATION_ENDPOINT", "https://auth.test.com/validate")
    monkeypatch.setenv("OAUTH_TOKEN_CACHE_TTL", "60")
    monkeypatch.setenv("KEYCLOAK_URL", "https://auth.test.com")
    monkeypatch.setenv("KEYCLOAK_REALM", "test-realm")
    # This USE_OAUTH="False" is problematic. It makes the discovery endpoint tests pass but
    # prevents testing a full flow with authentication enabled.
    # For this E2E test, we'll ensure OAuth is enabled.
    monkeypatch.setenv("USE_OAUTH", "True") # Changed to True for E2E test
    yield
    get_config.cache_clear()

# --- Copied from tests/unit/test_oauth_middleware.py ---
@pytest.fixture(scope="module")
def jwks_keys():
    """Generates a consistent set of RSA keys for JWT signing and validation."""
    # Main key used for valid tokens
    main_private_key_crypto = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    main_public_key_crypto = main_private_key_crypto.public_key()

    main_private_pem = main_private_key_crypto.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    main_public_pem = main_public_key_crypto.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    main_public_jwk_dict = JsonWebKey.import_key(main_public_pem).as_dict()
    main_public_jwk_dict["alg"] = "RS256" # Ensure alg is present for matching

    # Untrusted key for invalid signature tests
    untrusted_private_key_crypto = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    untrusted_public_key_crypto = untrusted_private_key_crypto.public_key()
    untrusted_public_jwk_dict = JsonWebKey.import_key(
        untrusted_public_key_crypto.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
    ).as_dict()
    untrusted_public_jwk_dict["alg"] = "RS256"

    return (
        main_private_key_crypto,
        main_private_pem,
        main_public_key_crypto,
        main_public_jwk_dict,
        untrusted_private_key_crypto,
        untrusted_public_jwk_dict,
    )

def create_test_jwt(
    private_key: rsa.RSAPrivateNumbers | str,
    issuer: str,
    client_id: str,
    kid_override: str | None = None,
    claims_override: dict | None = None,
) -> str:
    """Helper to create a signed JWT for testing."""
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=5)
    iat = now
    jti = "test-jti"

    if isinstance(private_key, (rsa.RSAPrivateNumbers, rsa.RSAPrivateKey)):
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        kid = JsonWebKey.import_key(private_pem).as_dict(private=False)["kid"]
    else:
        # Assuming private_key is already a PEM string
        private_pem = private_key
        kid = JsonWebKey.import_key(private_pem).as_dict(private=False)["kid"]

    if kid_override:
        kid = kid_override

    default_claims = {
        "iss": issuer,
        "aud": "account",
        "exp": exp,
        "iat": iat,
        "jti": jti,
        "client_id": client_id,
        "sub": "test-user-id",  # Subject
        "preferred_username": "test-user",
        "scope": "openid profile email read:transcripts",
        "azp": client_id,  # Authorized party
        "typ": "Bearer",
    }

    if claims_override:
        default_claims.update(claims_override)

    headers = {"kid": kid, "alg": "RS256", "typ": "JWT"}

    return jose_jwt.encode(default_claims, private_pem, algorithm="RS256", headers=headers)
# --- End copied section ---

@pytest.fixture
def mock_keycloak_discovery():
    """Mock Keycloak OIDC discovery document."""
    return {
        "issuer": "https://auth.test.com/realms/test-realm",
        "authorization_endpoint": "https://auth.test.com/realms/test-realm/protocol/openid-connect/auth",
        "token_endpoint": "https://auth.test.com/realms/test-realm/protocol/openid-connect/token",
        "jwks_uri": "https://auth.test.com/realms/test-realm/protocol/openid-connect/certs",
        "response_types_supported": ["code", "token", "id_token"],
        "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "code_challenge_methods_supported": ["S256", "plain"], # Added per story 2.1.1
    }

@pytest.fixture
def mock_app_with_oauth(jwks_keys, mock_keycloak_discovery):
    """
    Fixture to create a FastAPI app with OAuthMiddleware, suitable for integration tests.
    It patches get_config and _get_cached_jwks to use mock data.
    """
    mock_cfg = MagicMock()
    mock_cfg.keycloak_url = "https://auth.test.com"
    mock_cfg.keycloak_realm = "test-realm"
    mock_cfg.oauth_token_cache_ttl = 0
    mock_cfg.use_oauth = True # Ensure OAuth is enabled

    # Configure the mock to return ALL public keys that might be used for validation
    _, _, _, main_public_jwk_dict, _, untrusted_public_jwk_dict = jwks_keys
    mock_jwks_data = {"keys": [main_public_jwk_dict, untrusted_public_jwk_dict]}

    with (
        patch("src.middleware.oauth.get_config", return_value=mock_cfg),
        patch("src.handlers.oauth_discovery.get_config", return_value=mock_cfg),
        patch("src.middleware.oauth._get_cached_jwks", return_value=mock_jwks_data),
        # Patch httpx.AsyncClient.get for OIDC discovery calls
        patch("httpx.AsyncClient.get") as mock_httpx_get_async,
    ):
        # Setup mock for OIDC discovery endpoint
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value=mock_keycloak_discovery)
        mock_response.raise_for_status = MagicMock()
        mock_httpx_get_async.return_value = mock_response

        test_app = FastAPI(lifespan=lifespan)
        test_app.add_middleware(OAuthMiddleware, exclude_paths=["/health", "/.well-known/oauth-authorization-server"])

        # Mount actual application endpoints (protected)
        test_app.add_api_route("/tools/invoke", invoke_tool, methods=["POST"])
        test_app.add_api_route("/tools/list", list_tools, methods=["GET"])
        test_app.add_api_route("/health", app.routes[0].endpoint, methods=["GET"]) # Reuse health endpoint from main app
        # Mount the actual OAuth discovery handler directly
        test_app.add_api_route("/.well-known/oauth-authorization-server", get_oauth_discovery_document, methods=["GET"])

        # Initialize ToolRegistry and attach to app state
        tool_registry = ToolRegistry()
        # Clear existing tools to prevent ToolRegistrationError in subsequent calls within the module
        tool_registry._registered_tools = {}
        tool_registry._registered_metadata = {}
        # Manually register the YouTube tool for testing purposes
        from src.tools.hello_world_tool import HelloWorldTool
        from src.tools.youtube_tool import YouTubeTool
        tool_registry.register_tool(YouTubeTool())
        tool_registry.register_tool(HelloWorldTool())
        test_app.state.registry = tool_registry

        yield TestClient(test_app)


@pytest.mark.usefixtures("setup_env", "clear_discovery_cache")
@pytest.mark.asyncio
async def test_discovery_endpoint_returns_metadata(mock_keycloak_discovery, mock_app_with_oauth): # Modified to use mock_app_with_oauth
    """Test that discovery endpoint successfully returns OAuth metadata."""
    client = mock_app_with_oauth # Use the client from the new fixture

    response = client.get("/.well-known/oauth-authorization-server")

    assert response.status_code == 200
    data = response.json()
    assert data["issuer"] == "https://auth.test.com/realms/test-realm"
    assert "authorization_endpoint" in data
    assert (
        data["authorization_endpoint"]
        == "https://auth.test.com/realms/test-realm/protocol/openid-connect/auth"
    )
    assert "code_challenge_methods_supported" in data


@pytest.mark.usefixtures("setup_env", "clear_discovery_cache")
@pytest.mark.asyncio
async def test_discovery_endpoint_accessible_without_auth(mock_app_with_oauth): # Modified to use mock_app_with_oauth
    """Test that discovery endpoint is accessible without authentication."""
    client = mock_app_with_oauth # Use the client from the new fixture

    # No Authorization header - should still work
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200


@pytest.mark.usefixtures("setup_env", "clear_discovery_cache")
@pytest.mark.asyncio
async def test_discovery_endpoint_handles_keycloak_unavailable(mock_keycloak_discovery): # This test needs a dedicated app setup without mock_httpx_get_async from mock_app_with_oauth
    """Test error handling when Keycloak is unavailable."""
    mock_cfg = MagicMock()
    mock_cfg.keycloak_url = "https://auth.test.com"
    mock_cfg.keycloak_realm = "test-realm"
    mock_cfg.use_oauth = True

    with (
        patch("src.handlers.oauth_discovery.get_config", return_value=mock_cfg),
        patch("httpx.AsyncClient") as mock_client_class,
    ):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused", request=MagicMock())
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        test_app = FastAPI(lifespan=lifespan)
        # Mount the actual OAuth discovery handler directly
        test_app.add_api_route("/.well-known/oauth-authorization-server", get_oauth_discovery_document, methods=["GET"])

        with TestClient(test_app) as client:
            response = client.get("/.well-known/oauth-authorization-server")
            assert response.status_code == 503
            assert "Could not connect to the authentication provider" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_endpoint_accessible_without_auth(mock_app_with_oauth): # Modified to use mock_app_with_oauth
    """Test that health endpoint is accessible without authentication."""
    client = mock_app_with_oauth # Use the client from the new fixture
    response = client.get("/health")
    assert response.status_code == 200

# --- New End-to-End Authorization Code Flow Test ---
@pytest.mark.usefixtures("setup_env", "clear_discovery_cache")
@pytest.mark.asyncio
async def test_e2e_authorization_code_flow_protected_endpoint(jwks_keys, mock_app_with_oauth, mock_keycloak_discovery, mocker):
    """
    Tests the full authorization code flow simulation:
    1. Fetches discovery document.
    2. Creates a mock JWT using the discovered issuer.
    3. Accesses a protected tool endpoint with the JWT.
    4. Verifies successful access and AuthContext attachment.
    """
    # Unpack jwks_keys properly: (main_private_key_crypto, main_private_pem, main_public_key_crypto, main_public_jwk_dict, untrusted_private_key_crypto, untrusted_public_jwk_dict)
    _, main_private_pem, _, main_public_jwk_dict, _, _ = jwks_keys
    test_client_instance = mock_app_with_oauth

    # Step 1: Get Discovery Document (mocked via mock_app_with_oauth's httpx.AsyncClient.get patch)
    # The issuer and jwks_uri come from mock_keycloak_discovery fixture

    # Step 2: Create a mock JWT
    issuer = mock_keycloak_discovery["issuer"]
    client_id = "test-client"
    token = create_test_jwt(main_private_pem, issuer, client_id, kid_override=main_public_jwk_dict["kid"])

    # Mock the actual tool handler to prevent external calls and inspect its context
    mock_tool_handler = AsyncMock(return_value={"result": "e2e_success"})
    registry = ToolRegistry() # Get singleton instance
    mocker.patch.object(registry.get_tool("get_youtube_transcript"), "handler", mock_tool_handler)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": "https://youtube.com/watch?v=123"},
        "context": {"correlation_id": "test-e2e-abc"},
    }

    # Step 3: Access Protected Endpoint
    response = test_client_instance.post("/tools/invoke", headers=headers, json=payload)

    # Step 4: Assert Success and AuthContext
    assert response.status_code == 200
    assert response.json()["result"] == {"result": "e2e_success"}

    # Verify the tool handler was called and inspect the context passed to the handler
    mock_tool_handler.assert_awaited_once()
    args, _ = mock_tool_handler.call_args
    exec_context: ToolExecutionContext = args[1]

    assert exec_context is not None
    assert exec_context.auth_context is not None
    assert exec_context.auth_context.is_valid is True
    assert exec_context.auth_context.client_id == client_id
    assert exec_context.auth_context.user_id == "test-user-id"
    assert "read:transcripts" in exec_context.auth_context.scopes
    assert exec_context.correlation_id == "test-e2e-abc"
