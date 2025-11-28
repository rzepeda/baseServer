"""Unit tests for OAuth Discovery endpoint handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
import httpx

from src.handlers.oauth_discovery import get_oauth_discovery_document, _cached_metadata


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the global cache before each test."""
    import src.handlers.oauth_discovery as discovery_module
    discovery_module._cached_metadata = None
    yield
    discovery_module._cached_metadata = None


@pytest.fixture
def mock_keycloak_metadata():
    """Sample OIDC discovery metadata from Keycloak."""
    return {
        "issuer": "https://auth.example.com/realms/myrealm",
        "authorization_endpoint": "https://auth.example.com/realms/myrealm/protocol/openid-connect/auth",
        "token_endpoint": "https://auth.example.com/realms/myrealm/protocol/openid-connect/token",
        "jwks_uri": "https://auth.example.com/realms/myrealm/protocol/openid-connect/certs",
        "response_types_supported": ["code", "token", "id_token"],
        "grant_types_supported": ["authorization_code", "client_credentials", "refresh_token"],
    }


@pytest.mark.asyncio
async def test_discovery_endpoint_success(mock_keycloak_metadata, mocker):
    """Test successful fetch of OAuth discovery metadata."""
    mock_config = mocker.MagicMock()
    mock_config.keycloak_url = "https://auth.example.com"
    mock_config.keycloak_realm = "myrealm"

    mocker.patch("src.handlers.oauth_discovery.get_config", return_value=mock_config)

    mock_response = AsyncMock()
    mock_response.json = MagicMock(return_value=mock_keycloak_metadata)
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await get_oauth_discovery_document()

    assert result["issuer"] == "https://auth.example.com/realms/myrealm"
    assert result["authorization_endpoint"] == "https://auth.example.com/realms/myrealm/protocol/openid-connect/auth"
    assert "code_challenge_methods_supported" in result


@pytest.mark.asyncio
async def test_discovery_endpoint_adds_pkce_support(mocker):
    """Test that PKCE support is added if not present in Keycloak metadata."""
    mock_config = mocker.MagicMock()
    mock_config.keycloak_url = "https://auth.example.com"
    mock_config.keycloak_realm = "myrealm"

    mocker.patch("src.handlers.oauth_discovery.get_config", return_value=mock_config)

    metadata_without_pkce = {
        "issuer": "https://auth.example.com/realms/myrealm",
        "authorization_endpoint": "https://auth.example.com/realms/myrealm/protocol/openid-connect/auth",
    }

    mock_response = AsyncMock()
    mock_response.json = MagicMock(return_value=metadata_without_pkce)
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await get_oauth_discovery_document()

    assert "code_challenge_methods_supported" in result
    assert result["code_challenge_methods_supported"] == ["S256", "plain"]


@pytest.mark.asyncio
async def test_discovery_endpoint_caches_metadata(mock_keycloak_metadata, mocker):
    """Test that metadata is cached after first fetch."""
    mock_config = mocker.MagicMock()
    mock_config.keycloak_url = "https://auth.example.com"
    mock_config.keycloak_realm = "myrealm"

    mocker.patch("src.handlers.oauth_discovery.get_config", return_value=mock_config)

    mock_response = AsyncMock()
    mock_response.json = MagicMock(return_value=mock_keycloak_metadata)
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client) as mock_httpx:
        # First call - should fetch from Keycloak
        result1 = await get_oauth_discovery_document()
        assert mock_httpx.called

        # Second call - should use cache
        mock_httpx.reset_mock()
        result2 = await get_oauth_discovery_document()
        assert not mock_httpx.called  # Should not make HTTP request

        assert result1 == result2


@pytest.mark.asyncio
async def test_discovery_endpoint_handles_network_error(mocker):
    """Test error handling when Keycloak is unreachable."""
    mock_config = mocker.MagicMock()
    mock_config.keycloak_url = "https://auth.example.com"
    mock_config.keycloak_realm = "myrealm"

    mocker.patch("src.handlers.oauth_discovery.get_config", return_value=mock_config)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            await get_oauth_discovery_document()

        assert exc_info.value.status_code == 503
        assert "Could not connect to the authentication provider" in exc_info.value.detail


@pytest.mark.asyncio
async def test_discovery_endpoint_handles_http_error(mocker):
    """Test error handling for HTTP errors from Keycloak."""
    mock_config = mocker.MagicMock()
    mock_config.keycloak_url = "https://auth.example.com"
    mock_config.keycloak_realm = "myrealm"

    mocker.patch("src.handlers.oauth_discovery.get_config", return_value=mock_config)

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("404 Not Found", request=None, response=None)
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            await get_oauth_discovery_document()

        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_discovery_endpoint_handles_unexpected_error(mocker):
    """Test error handling for unexpected errors."""
    mock_config = mocker.MagicMock()
    mock_config.keycloak_url = "https://auth.example.com"
    mock_config.keycloak_realm = "myrealm"

    mocker.patch("src.handlers.oauth_discovery.get_config", return_value=mock_config)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Unexpected error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            await get_oauth_discovery_document()

        assert exc_info.value.status_code == 500
        assert "unexpected error" in exc_info.value.detail.lower()
