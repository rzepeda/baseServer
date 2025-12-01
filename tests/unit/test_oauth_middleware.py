from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from authlib.jose.rfc7517.jwk import JsonWebKey
from cryptography.hazmat.primitives import serialization  # Added to resolve NameError
from cryptography.hazmat.primitives.asymmetric import rsa  # Added to resolve NameError
from fastapi import FastAPI, Request
from jose import jwt as jose_jwt
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from src.middleware.oauth import OAuthMiddleware

# Import the original dispatch from conftest.py
from tests.conftest import _real_oauth_dispatch


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


@pytest.fixture(autouse=True)
def restore_oauth_middleware_dispatch():
    """Fixture to ensure the real OAuthMiddleware.dispatch is used for these tests."""
    original_dispatch = OAuthMiddleware.dispatch
    OAuthMiddleware.dispatch = _real_oauth_dispatch
    yield
    OAuthMiddleware.dispatch = original_dispatch


# --- Test Data and Mocks ---








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

    with (
        patch("src.middleware.oauth.get_config", return_value=mock_config),
        patch("src.middleware.oauth._get_cached_jwks") as mock_get_jwks,
    ):

        # Configure the mock to return ALL public keys that might be used for validation
        _, _, _, main_public_jwk_dict, _, untrusted_public_jwk_dict = jwks_keys
        mock_get_jwks.return_value = {"keys": [main_public_jwk_dict, untrusted_public_jwk_dict]}

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
    assert "Authorization header must be in 'Bearer <token>' format" in data["error_description"]


def test_invalid_jwt_signature_returns_401(isolated_app_client, jwks_keys, mock_config):
    """Verify that a JWT with an invalid signature is rejected."""
    _, main_private_pem, _, _, untrusted_private_key_crypto, untrusted_public_jwk_dict = jwks_keys

    # Generate a *third*, completely distinct private key
    # This key will be used to sign the token, but its public part is NOT in the JWKS
    temp_private_key_crypto = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    issuer = f"{mock_config.keycloak_url}/realms/{mock_config.keycloak_realm}"

    # Sign the token using the temp_private_key_crypto, but force the KID in the header
    # to be untrusted_public_jwk_dict['kid'] so the middleware can find a key
    token = create_test_jwt(
        temp_private_key_crypto, issuer, "test-client", kid_override=untrusted_public_jwk_dict["kid"]
    )

    response = isolated_app_client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_token"
    assert "Token validation failed: bad_signature: " in data["error_description"]


def test_expired_jwt_returns_401(isolated_app_client, jwks_keys, mock_config):
    """Verify that an expired JWT is rejected."""
    _, main_private_pem, _, _, _, _ = jwks_keys
    issuer = f"{mock_config.keycloak_url}/realms/{mock_config.keycloak_realm}"

    # Create an expired token
    exp_claims = {"exp": datetime.now(UTC) - timedelta(minutes=1)}
    token = create_test_jwt(main_private_pem, issuer, "test-client", claims_override=exp_claims)

    response = isolated_app_client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_token"
    assert (
        "Token validation failed: expired_token: The token is expired" in data["error_description"]
    )


def test_incorrect_issuer_returns_401(isolated_app_client, jwks_keys, mock_config):
    """Verify that a JWT with an incorrect issuer is rejected."""
    _, main_private_pem, _, _, _, _ = jwks_keys

    # Create a token with a wrong issuer
    token = create_test_jwt(main_private_pem, "https://wrong.issuer.com", "test-client")

    response = isolated_app_client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["error"] == "invalid_token"
    assert (
        "Token validation failed: invalid_claim: Invalid claim 'iss'" in data["error_description"]
    )


def test_valid_jwt_succeeds_and_attaches_auth_context(isolated_app_client, jwks_keys, mock_config):
    """Verify that a valid JWT passes and the auth context is attached to the request."""
    _, main_private_pem, _, _, _, _ = jwks_keys
    issuer = f"{mock_config.keycloak_url}/realms/{mock_config.keycloak_realm}"

    token = create_test_jwt(main_private_pem, issuer, "test-client")

    response = isolated_app_client.get("/", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["client_id"] == "test-client"


# --- Caching Tests ---


@patch("httpx.get")
def test_jwks_caching(mock_httpx_get, jwks_keys):
    """Verify that the JWKS fetching is cached."""
    from src.middleware.oauth import _get_cached_jwks as uncached_fn

    uncached_fn.cache_clear()  # Clear lru_cache

    # Configure mock httpx.get to return the public key
    _, _, _, _, _, untrusted_public_jwk_dict = jwks_keys
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "keys": [untrusted_public_jwk_dict]
    }  # Use untrusted_public_jwk_dict for mocking JWKS fetch
    mock_httpx_get.return_value = mock_response

    jwks_uri = "https://my-test-jwks.com/.well-known/jwks.json"

    # Call multiple times
    uncached_fn(jwks_uri)
    uncached_fn(jwks_uri)

    # Assert that the underlying httpx.get was only called once
    mock_httpx_get.assert_called_once_with(jwks_uri, timeout=5.0)
