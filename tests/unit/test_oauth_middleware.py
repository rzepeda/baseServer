import hashlib
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from src.middleware.oauth import (
    OAuthError,
    OAuthMiddleware,
    TokenCache,
    validate_token_with_provider,
)
from src.models.auth import AuthContext, OAuthConfig
from tests.conftest import _real_oauth_dispatch

# This file is now active. The global skip has been removed.


@pytest.fixture
def test_oauth_config() -> OAuthConfig:
    """Provides a consistent OAuth configuration for tests."""
    return OAuthConfig(
        provider_url="https://test-oauth.com",
        client_id="test-client",
        client_secret="test-secret",
        scopes=["read:transcripts"],
        validation_endpoint="https://test-oauth.com/validate",
    )


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Provides a mock of httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


# --- TokenCache Unit Tests (Unchanged) ---


def test_token_cache_set_and_get():
    cache = TokenCache(ttl_seconds=10)
    token_hash = "testhash"
    auth_context = AuthContext(
        is_valid=True, token_hash=token_hash, scopes=["s1"], client_id="c1", expires_at=None
    )
    cache.set(token_hash, auth_context)
    assert cache.get(token_hash) == auth_context


def test_token_cache_expiration():
    cache = TokenCache(ttl_seconds=0.01)
    token_hash = "testhash"
    auth_context = AuthContext(
        is_valid=True, token_hash=token_hash, scopes=["s1"], client_id="c1", expires_at=None
    )
    cache.set(token_hash, auth_context)
    time.sleep(0.02)
    assert cache.get(token_hash) is None


def test_token_cache_delete():
    cache = TokenCache(ttl_seconds=10)
    token_hash = "testhash"
    auth_context = AuthContext(
        is_valid=True, token_hash=token_hash, scopes=["s1"], client_id="c1", expires_at=None
    )
    cache.set(token_hash, auth_context)
    cache.delete(token_hash)
    assert cache.get(token_hash) is None


def test_token_cache_disabled():
    cache = TokenCache(ttl_seconds=0)
    token_hash = "testhash"
    auth_context = AuthContext(
        is_valid=True, token_hash=token_hash, scopes=["s1"], client_id="c1", expires_at=None
    )
    cache.set(token_hash, auth_context)
    assert cache.get(token_hash) is None


# --- Standalone `validate_token_with_provider` Unit Tests ---


@pytest.mark.asyncio
async def test_validate_token_success(test_oauth_config, mock_httpx_client):
    """Tests successful token validation."""
    token = "valid_token"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    exp_time = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    mock_httpx_client.post.return_value = httpx.Response(
        200,
        json={
            "active": True,
            "scope": "read:transcripts",
            "client_id": "test-client-id",
            "exp": exp_time,
        },
        request=httpx.Request("POST", str(test_oauth_config.validation_endpoint)),
    )

    result_context = await validate_token_with_provider(
        token, token_hash, test_oauth_config, mock_httpx_client
    )

    mock_httpx_client.post.assert_awaited_once()
    assert result_context.is_valid is True
    assert result_context.client_id == "test-client-id"
    assert result_context.scopes == ["read:transcripts"]
    assert result_context.token_hash == token_hash


@pytest.mark.asyncio
async def test_validate_token_inactive(test_oauth_config, mock_httpx_client):
    """Tests validation failure for an inactive token."""
    token = "inactive_token"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    mock_httpx_client.post.return_value = httpx.Response(
        200,
        json={"active": False},
        request=httpx.Request("POST", str(test_oauth_config.validation_endpoint)),
    )

    with pytest.raises(OAuthError) as exc_info:
        await validate_token_with_provider(token, token_hash, test_oauth_config, mock_httpx_client)

    assert exc_info.value.status_code == 401
    assert exc_info.value.error == "invalid_token"


@pytest.mark.asyncio
async def test_validate_token_http_401_error(test_oauth_config, mock_httpx_client):
    """Tests validation failure when provider returns 401."""
    token = "invalid_token"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    mock_request = httpx.Request("POST", str(test_oauth_config.validation_endpoint))
    mock_response = httpx.Response(
        401,
        json={"error": "invalid_token", "error_description": "The token is wrong"},
        request=mock_request,
    )
    mock_httpx_client.post.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=mock_request, response=mock_response
    )

    with pytest.raises(OAuthError) as exc_info:
        await validate_token_with_provider(token, token_hash, test_oauth_config, mock_httpx_client)

    assert exc_info.value.status_code == 401
    assert exc_info.value.error == "invalid_token"
    assert exc_info.value.description == "The token is wrong"


@pytest.mark.asyncio
async def test_validate_token_timeout(test_oauth_config, mock_httpx_client):
    """Tests timeout during token validation."""
    token = "timeout_token"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    mock_httpx_client.post.side_effect = httpx.TimeoutException("Connection timed out")

    with pytest.raises(OAuthError) as exc_info:
        await validate_token_with_provider(token, token_hash, test_oauth_config, mock_httpx_client)

    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.description


# --- Middleware Behavior Tests (using isolated TestClient) ---




@pytest.fixture
def isolated_client(monkeypatch, test_oauth_config):
    """
    Creates a clean FastAPI TestClient with OAuthMiddleware for isolated testing.
    This fixture temporarily un-patches the session-wide OAuth bypass to test
    the real middleware logic.
    """
    # Temporarily undo the session-wide patch to test real middleware logic
    original_dispatch = OAuthMiddleware.dispatch
    OAuthMiddleware.dispatch = _real_oauth_dispatch

    try:
        # Mock get_config for this specific test client scope
        mock_cfg = MagicMock()
        mock_cfg.oauth_config = test_oauth_config
        mock_cfg.oauth_token_cache_ttl = 60
        monkeypatch.setattr("src.middleware.oauth.get_config", lambda: mock_cfg)

        app = FastAPI()

        # This is the target app the middleware will call `call_next` on
        @app.api_route("/{path:path}")
        async def catch_all(request: Request):
            auth_context = getattr(request.state, "auth_context", None)
            client_id = auth_context.client_id if auth_context else "none"
            return JSONResponse({"status": "ok", "auth_client_id": client_id})

        # Add the real middleware
        app.add_middleware(OAuthMiddleware, exclude_paths=["/health"])

        yield TestClient(app)

    finally:
        # Restore the session-wide patch so other tests are not affected
        OAuthMiddleware.dispatch = original_dispatch


def test_middleware_missing_token(isolated_client):
    response = isolated_client.get("/")
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_request"
    assert "Authorization header is missing" in response.json()["error_description"]


def test_middleware_malformed_header(isolated_client):
    response = isolated_client.get("/", headers={"Authorization": "NotBearer token"})
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_request"
    assert "must be in 'Bearer <token>' format" in response.json()["error_description"]


def test_middleware_health_check_unauthenticated(isolated_client):
    response = isolated_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_middleware_token_caching(isolated_client, monkeypatch):
    token = "a_cachable_token"

    # Mock the validation function itself for this test
    mock_validator = AsyncMock()
    exp_time = datetime.now(UTC) + timedelta(hours=1)
    mock_validator.return_value = AuthContext(
        is_valid=True,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        scopes=["read:all"],
        expires_at=exp_time,
        client_id="cached-client",
    )
    monkeypatch.setattr("src.middleware.oauth.validate_token_with_provider", mock_validator)

    # First call, should trigger validation
    response1 = isolated_client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response1.status_code == 200
    assert response1.json()["auth_client_id"] == "cached-client"
    mock_validator.assert_awaited_once()

    # Second call, should be a cache hit
    response2 = isolated_client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert response2.status_code == 200
    assert response2.json()["auth_client_id"] == "cached-client"
    mock_validator.assert_awaited_once()  # Assert it was NOT called again


def test_middleware_end_to_end_valid_token(isolated_client, monkeypatch):
    token = "e2e_valid_token"
    mock_validator = AsyncMock()
    exp_time = datetime.now(UTC) + timedelta(hours=1)
    mock_validator.return_value = AuthContext(
        is_valid=True,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        scopes=["read:all"],
        expires_at=exp_time,
        client_id="e2e-client",
    )
    monkeypatch.setattr("src.middleware.oauth.validate_token_with_provider", mock_validator)

    response = isolated_client.get("/", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["auth_client_id"] == "e2e-client"
    mock_validator.assert_awaited_once()
