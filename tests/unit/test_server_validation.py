"""Test parameter validation in server.py."""


import pytest
from fastapi.testclient import TestClient
from starlette import status

from src.server import app

pytestmark = pytest.mark.usefixtures("bypass_oauth_for_most_tests")


@pytest.fixture(scope="module")
def client():
    """Test client with mocked OAuth middleware from session fixture."""
    with TestClient(app) as c:
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
