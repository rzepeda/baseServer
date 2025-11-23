"""Unit tests for the health check handler."""


from fastapi.testclient import TestClient

from src.server import app


def test_health_check() -> None:

    """

    Tests that the /health endpoint returns a successful response.

    """

    with TestClient(app) as client:

        response = client.get("/health")



    assert response.status_code == 200



    response_json = response.json()



    assert response_json["status"] == "healthy"

    assert response_json["version"] == "0.1.0"

    assert "timestamp" in response_json

    assert "tools_loaded" in response_json

    assert "registered_tools" in response_json

