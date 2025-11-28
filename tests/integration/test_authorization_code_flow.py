"""Integration test for Authorization Code Flow with OAuth Discovery."""

import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient
import httpx

from src.server import app
from src.config import get_config


@pytest.fixture(autouse=True)
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
    monkeypatch.setenv("USE_OAUTH", "False")  # Disable OAuth for discovery endpoint test
    yield
    get_config.cache_clear()


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
    }


@pytest.mark.asyncio
async def test_discovery_endpoint_returns_metadata(mock_keycloak_discovery):
    """Test that discovery endpoint successfully returns OAuth metadata."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_keycloak_discovery
        mock_response.raise_for_status = AsyncMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_client_class.return_value = mock_client

        with TestClient(app) as client:
            response = client.get("/.well-known/oauth-authorization-server")

            assert response.status_code == 200
            data = response.json()
            assert data["issuer"] == "https://auth.test.com/realms/test-realm"
            assert "authorization_endpoint" in data
            assert data["authorization_endpoint"] == "https://auth.test.com/realms/test-realm/protocol/openid-connect/auth"
            assert "code_challenge_methods_supported" in data


@pytest.mark.asyncio
async def test_discovery_endpoint_accessible_without_auth():
    """Test that discovery endpoint is accessible without authentication."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "issuer": "https://auth.test.com/realms/test-realm",
            "authorization_endpoint": "https://auth.test.com/realms/test-realm/protocol/openid-connect/auth",
        }
        mock_response.raise_for_status = AsyncMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_client_class.return_value = mock_client

        with TestClient(app) as client:
            # No Authorization header - should still work
            response = client.get("/.well-known/oauth-authorization-server")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_discovery_endpoint_handles_keycloak_unavailable():
    """Test error handling when Keycloak is unavailable."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        mock_client_class.return_value = mock_client

        with TestClient(app) as client:
            response = client.get("/.well-known/oauth-authorization-server")
            assert response.status_code == 503
            assert "Could not connect to the authentication provider" in response.json()["detail"]


def test_health_endpoint_accessible_without_auth():
    """Test that health endpoint is accessible without authentication."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
