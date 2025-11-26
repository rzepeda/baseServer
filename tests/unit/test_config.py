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
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("OAUTH_ISSUER_URL", raising=False)
    monkeypatch.delenv("OAUTH_AUDIENCE", raising=False)
    monkeypatch.setenv("CLOUDFLARE_TUNNEL_URL", "https://agentictools.uk")
    config = Config(
        oauth_issuer_url="test",
        oauth_audience="test",
        _env_file=None,  # Disable .env file loading for isolated test
    )
    assert config.server_host == "0.0.0.0"
    assert config.mcp_port == 8080
    assert config.rest_api_port == 8081
    assert config.log_level == "INFO"
    assert config.environment == "development"
    assert config.oauth_token_cache_ttl == 60
    assert config.cloudflare_tunnel_url == "https://agentictools.uk"


def test_config_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables override default values."""
    monkeypatch.setenv("SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "9000")
    monkeypatch.setenv("REST_API_PORT", "9001")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("OAUTH_TOKEN_CACHE_TTL", "300")
    monkeypatch.setenv("OAUTH_ISSUER_URL", "http://localhost")
    monkeypatch.setenv("OAUTH_AUDIENCE", "my-api")
    monkeypatch.setenv("CLOUDFLARE_TUNNEL_URL", "http://new-tunnel.com")

    config = get_config()

    assert config.server_host == "127.0.0.1"
    assert config.mcp_port == 9000
    assert config.rest_api_port == 9001
    assert config.log_level == "DEBUG"
    assert config.environment == "production"
    assert config.oauth_token_cache_ttl == 300
    assert config.oauth_issuer_url == "http://localhost"
    assert config.oauth_audience == "my-api"
    assert config.cloudflare_tunnel_url == "http://new-tunnel.com"


def test_config_missing_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that validation fails if required fields are missing."""
    monkeypatch.delenv("OAUTH_ISSUER_URL", raising=False)
    monkeypatch.delenv("OAUTH_AUDIENCE", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        Config(_env_file=None)  # Disable .env file loading to test required fields
    errors = excinfo.value.errors()
    assert len(errors) == 2
    error_fields = {error["loc"][0] for error in errors}
    assert "oauth_issuer_url" in error_fields
    assert "oauth_audience" in error_fields


def test_get_config_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the get_config function caches its result."""
    monkeypatch.setenv("OAUTH_ISSUER_URL", "http://test.com")
    monkeypatch.setenv("OAUTH_AUDIENCE", "test-api")

    config1 = get_config()
    config2 = get_config()
    assert config1 is config2

    monkeypatch.setenv("MCP_PORT", "5000")
    # The config should not change because it's cached
    config3 = get_config()
    assert config3.mcp_port == 8080  # Default value
    assert config1 is config3

    # The cache can be cleared for new config to be loaded.
    get_config.cache_clear()
    config4 = get_config()
    assert config4.mcp_port == 5000
    assert config1 is not config4
