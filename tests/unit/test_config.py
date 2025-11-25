"""Unit tests for the configuration module."""

import pytest
from pydantic import ValidationError

from src.config import Config, get_config


@pytest.fixture(autouse=True)
def clear_config_cache() -> None:
    """Clear the config cache before and after each test."""
    get_config.cache_clear()
    yield
    get_config.cache_clear()


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the Config class loads default values correctly."""
    # Temporarily remove env vars set by conftest to test defaults
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("CLOUDFLARE_TUNNEL_URL", raising=False)

    # These are now required, so we must provide them for the test
    monkeypatch.setenv("OAUTH_PROVIDER_URL", "https://default.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "default_id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "default_secret")
    monkeypatch.setenv("OAUTH_SCOPES", "default_scope")
    monkeypatch.setenv("OAUTH_VALIDATION_ENDPOINT", "https://default.com/validate")

    config = Config(_env_file=None)

    assert config.server_host == "0.0.0.0"
    assert config.mcp_port == 8080
    assert config.rest_api_port == 8081
    assert config.log_level == "INFO"
    assert config.environment == "development"
    assert config.oauth_token_cache_ttl == 60
    assert (
        config.cloudflare_tunnel_url
        == "https://frequently-introducing-segment-keep.trycloudflare.com/mcp"
    )

    # Test the oauth_config property
    oauth_config = config.oauth_config
    assert str(oauth_config.provider_url) == "https://default.com/"
    assert oauth_config.client_id == "default_id"
    assert oauth_config.client_secret.get_secret_value() == "default_secret"
    assert oauth_config.scopes == ["default_scope"]
    assert str(oauth_config.validation_endpoint) == "https://default.com/validate"


def test_config_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables override default values."""
    monkeypatch.setenv("SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "9000")
    monkeypatch.setenv("REST_API_PORT", "9001")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CLOUDFLARE_TUNNEL_URL", "http://new-tunnel.com")

    # Override OAuth vars set by conftest
    monkeypatch.setenv("OAUTH_PROVIDER_URL", "https://prod.oauth.com")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "prod_id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "prod_secret")
    monkeypatch.setenv("OAUTH_SCOPES", "scope1,scope2")
    monkeypatch.setenv("OAUTH_VALIDATION_ENDPOINT", "https://prod.oauth.com/introspect")
    monkeypatch.setenv("OAUTH_TOKEN_CACHE_TTL", "300")

    config = get_config()

    assert config.server_host == "127.0.0.1"
    assert config.mcp_port == 9000
    assert config.rest_api_port == 9001
    assert config.log_level == "DEBUG"
    assert config.environment == "production"
    assert config.oauth_token_cache_ttl == 300
    assert config.cloudflare_tunnel_url == "http://new-tunnel.com"

    oauth_config = config.oauth_config
    assert str(oauth_config.provider_url) == "https://prod.oauth.com/"
    assert oauth_config.client_id == "prod_id"
    assert oauth_config.client_secret.get_secret_value() == "prod_secret"
    assert oauth_config.scopes == ["scope1", "scope2"]
    assert str(oauth_config.validation_endpoint) == "https://prod.oauth.com/introspect"


def test_config_missing_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that validation fails if required fields are missing."""
    # Unset the environment variables that are set in conftest.py
    monkeypatch.delenv("OAUTH_PROVIDER_URL", raising=False)
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_SCOPES", raising=False)
    monkeypatch.delenv("OAUTH_VALIDATION_ENDPOINT", raising=False)

    with pytest.raises(ValidationError) as excinfo:
        Config(_env_file=None)

    errors = excinfo.value.errors()
    assert len(errors) == 5
    error_fields = {error["loc"][0] for error in errors}
    assert "oauth_provider_url" in error_fields
    assert "oauth_client_id" in error_fields
    assert "oauth_client_secret" in error_fields
    assert "oauth_scopes" in error_fields
    assert "oauth_validation_endpoint" in error_fields


def test_get_config_is_cached() -> None:
    """Test that the get_config function caches its result."""
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2

    # The cache can be cleared for new config to be loaded.
    get_config.cache_clear()
    config3 = get_config()
    assert config1 is not config3
