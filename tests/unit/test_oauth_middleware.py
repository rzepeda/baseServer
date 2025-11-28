
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt as jose_jwt
from starlette.testclient import TestClient
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from src.middleware.oauth import OAuthMiddleware, OAuthError
from src.models.auth import AuthContext, OAuthConfig

# --- Test Data and Mocks ---

@pytest.fixture
def jwks_keys():
    """Fixture for a sample JWK private/public key pair."""
    # This is a sample RSA key for testing purposes only.
    private_key = {
        "kty": "RSA",
        "d": "d_val", "e": "AQAB", "n": "n_val",
        "p": "p_val", "q": "q_val",
        "dp": "dp_val", "dq": "dq_val", "qi": "qi_val"
    }
    public_key = {"kty": "RSA", "e": "AQAB", "n": "n_val", "kid": "test-key-id"}
    return private_key, public_key

def create_test_jwt(private_key, issuer, audience, claims_override=None):
    """Creates a signed JWT for testing."""
    now = datetime.now(UTC)
    claims = {
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(hours=1),
        "sub": "test-user-id",
        "client_id": "test-client",
        "scope": "read:transcripts"
    }
    if claims_override:
        claims.update(claims_override)
    
    headers = {"kid": private_key.get("kid", "test-key-id")}
    return jose_jwt.encode(claims, private_key, algorithm="RS256", headers=headers)

@pytest.fixture
def mock_config():
    """Fixture for a mocked application configuration."""
    cfg = MagicMock()
    cfg.keycloak_url = "https://test.keycloak.com"
    cfg.keycloak_realm = "test-realm"
    cfg.oauth_token_cache_ttl = 0  # Disable caching for most tests
    return cfg

@pytest.fixture
def isolated_app_client(mock_config, jwks_keys):
    """Creates a fully isolated FastAPI app with the OAuth middleware for testing."""
    
    with patch('src.middleware.oauth.get_config', return_value=mock_config), \
         patch('src.middleware.oauth._get_cached_jwks') as mock_get_jwks:

        # Configure the mock to return the public key
        _, public_key = jwks_keys
        mock_get_jwks.return_value = {"keys": [public_key]}
        
        app = FastAPI()
        
        # Add the middleware to be tested
        app.add_middleware(OAuthMiddleware, exclude_paths=["/health"])

        # A simple endpoint to verify the middleware is working
        @app.get("/")
        async def root(request: Request):
            auth_context = getattr(request.state, "auth_context", None)
            if auth_context:
                return JSONResponse({"status": "ok", "client_id": auth_context.client_id})
            return JSONResponse({"status": "ok", "client_id": None})
        
        @app.get("/health")
        async def health():
            return JSONResponse({"status": "healthy"})

        yield TestClient(app)


# --- Middleware Behavior Tests ---

def test_health_endpoint_is_excluded(isolated_app_client):
    """Verify that the /health endpoint is not protected by auth."""
    response = isolated_app_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_missing_auth_header_returns_401(isolated_app_client):
    """Verify that a request without an Authorization header is rejected."""
    response = isolated_app_client.get("/")
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_request"
    assert "Authorization header is missing" in data["error_description"]

def test_malformed_auth_header_returns_401(isolated_app_client):
    """Verify that a request with a malformed Authorization header is rejected."""
    response = isolated_app_client.get("/", headers={"Authorization": "Invalid value"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_request"
    assert "must be in 'Bearer <token> Perkenalkan" in data["error_description"]

def test_invalid_jwt_signature_returns_401(isolated_app_client, jwks_keys, mock_config):
    """Verify that a JWT with an invalid signature is rejected."""
    # Create a token with a different key
    wrong_private_key, _ = jwks_keys
    wrong_private_key = wrong_private_key.copy()
    wrong_private_key["d"] = "a_different_d_value"
    
    issuer = f"{mock_config.keycloak_url}/realms/{mock_config.keycloak_realm}"
    token = create_test_jwt(wrong_private_key, issuer, "account")
    
    response = isolated_app_client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_token"
    assert "Token validation failed: Signature verification failed" in data["error_description"]


def test_expired_jwt_returns_401(isolated_app_client, jwks_keys, mock_config):
    """Verify that an expired JWT is rejected."""
    private_key, _ = jwks_keys
    issuer = f"{mock_config.keycloak_url}/realms/{mock_config.keycloak_realm}"
    
    # Create an expired token
    exp_claims = {"exp": datetime.now(UTC) - timedelta(minutes=1)}
    token = create_test_jwt(private_key, issuer, "account", claims_override=exp_claims)
    
    response = isolated_app_client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_token"
    assert "Token has expired" in data["error_description"]

def test_incorrect_issuer_returns_401(isolated_app_client, jwks_keys, mock_config):
    """Verify that a JWT with an incorrect issuer is rejected."""
    private_key, _ = jwks_keys
    
    # Create a token with a wrong issuer
    token = create_test_jwt(private_key, "https://wrong.issuer.com", "account")
    
    response = isolated_app_client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_token"
    assert "Invalid issuer" in data["error_description"]

def test_valid_jwt_succeeds_and_attaches_auth_context(isolated_app_client, jwks_keys, mock_config):
    """Verify that a valid JWT passes and the auth context is attached to the request."""
    private_key, _ = jwks_keys
    issuer = f"{mock_config.keycloak_url}/realms/{mock_config.keycloak_realm}"
    
    token = create_test_jwt(private_key, issuer, "account")
    
    response = isolated_app_client.get("/", headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["client_id"] == "test-client"
# --- Caching Tests ---

@patch('src.middleware.oauth._get_cached_jwks')
def test_jwks_caching(mock_get_jwks, jwks_keys):
    """Verify that the JWKS fetching is cached."""
    # Need to clear the lru_cache for this test to be reliable
    from src.middleware.oauth import _get_cached_jwks as uncached_fn
    uncached_fn.cache_clear()

    _, public_key = jwks_keys
    mock_get_jwks.return_value = {"keys": [public_key]}
    
    jwks_uri = "https://my-test-jwks.com/.well-known/jwks.json"
    
    # Call multiple times
    uncached_fn(jwks_uri)
    uncached_fn(jwks_uri)
    
    # Assert that the underlying httpx call was only made once
    mock_get_jwks.assert_called_once_with(jwks_uri)
