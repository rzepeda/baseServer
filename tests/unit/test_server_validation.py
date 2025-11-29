"""Test parameter validation in server.py."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette import status

from src.config import get_config
from src.middleware.oauth import OAuthMiddleware
from src.registry.tool_registry import ToolRegistry, register_all_tools
from src.server import app as global_app

pytestmark = pytest.mark.usefixtures("bypass_oauth_for_most_tests")


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """
    Test client with OAuth middleware re-initialized to ensure it picks up the
    `bypass_oauth_for_most_tests` patch from conftest.py.
    """
    # Create a fresh FastAPI app instance for this test module
    # Copy the routes from the global app, but ensure middleware is reset
    test_app = FastAPI()
    for route in global_app.routes:
        test_app.routes.append(route)

    # Manually initialize ToolRegistry for test_app.state
    registry = ToolRegistry()
    test_app.state.registry = registry
    register_all_tools()  # Ensure tools are registered in this test instance

    # Re-add the OAuthMiddleware to the test_app
    config = get_config()
    if config.use_oauth:
        test_app.add_middleware(
            OAuthMiddleware,
            exclude_paths=[
                "/health",
                "/.well-known/oauth-authorization-server",
                "/.well-known/oauth-protected-resource",
                "/register",
            ],
        )

    with TestClient(test_app) as c:
        yield c


def test_missing_required_parameter(client: TestClient):
    """Test that missing required parameters are rejected."""
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {},  # Missing required 'url' parameter
    }

    response = client.post("/tools/invoke", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error_code"] == "invalid_parameters"
    assert "url" in response_json["error"].lower() or "required" in response_json["error"].lower()


def test_wrong_parameter_type(client: TestClient):
    """Test that parameters with wrong types are rejected."""
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": 12345},  # Should be string, not number
    }

    response = client.post("/tools/invoke", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error_code"] == "invalid_parameters"


def test_valid_parameters_accepted(client: TestClient):
    """Test that valid parameters are accepted (even if tool execution fails for other reasons)."""
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": "https://www.youtube.com/watch?v=test123"},
    }

    # This should pass validation (even though the video doesn't exist)
    response = client.post("/tools/invoke", json=payload)
    # Should not be a 400 validation error - will be 404 or 500 for actual execution
    assert (
        response.status_code != status.HTTP_400_BAD_REQUEST
        or response.json().get("error_code") != "invalid_parameters"
    )
