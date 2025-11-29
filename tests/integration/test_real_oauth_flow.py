import os

import httpx
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient  # Moved to top

from src.server import app  # Use the REST API server app # Moved to top

# SKIP: Manual integration test for real OAuth with Keycloak - not for automated testing
pytestmark = pytest.mark.skip(reason="Manual integration test - requires real Keycloak instance")

# Load environment variables from .env file
load_dotenv()


@pytest.fixture(scope="module")
def real_access_token():
    """
    Fixture to obtain a real access token from the OAuth provider.
    Fails the test if required environment variables are not found.
    """
    provider_url = os.getenv("OAUTH_PROVIDER_URL")
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")

    if not all([provider_url, client_id, client_secret]):
        pytest.fail(
            "Missing required OAuth environment variables in .env file. Please ensure OAUTH_PROVIDER_URL, OAUTH_CLIENT_ID, and OAUTH_CLIENT_SECRET are set."
        )

    try:
        with httpx.Client() as client:
            # Discover token endpoint
            discovery_url = f"{provider_url}/.well-known/openid-configuration"
            discovery_response = client.get(discovery_url)
            discovery_response.raise_for_status()
            token_endpoint = discovery_response.json()["token_endpoint"]

            # Get token
            token_payload = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
            token_response = client.post(token_endpoint, data=token_payload)
            token_response.raise_for_status()
            return token_response.json()["access_token"]
    except (httpx.RequestError, KeyError) as e:
        pytest.fail(f"Failed to get real access token: {e}")


@pytest.fixture(scope="module")
def client():
    """Test client that handles lifespan events."""
    with TestClient(app) as c:
        yield c


@pytest.mark.real_oauth
def test_middleware_with_real_token(client, real_access_token):
    """
    Tests the OAuthMiddleware with a real access token on a protected endpoint.
    """
    # Test with a valid token
    headers = {"Authorization": f"Bearer {real_access_token}"}
    response = client.get("/tools/list", headers=headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.real_oauth
def test_middleware_with_invalid_token(client):
    """
    Tests the OAuthMiddleware with an invalid token.
    """
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/tools/list", headers=headers)
    assert response.status_code == 401
