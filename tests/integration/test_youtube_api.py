import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette import status

from src.server import app
# from src.middleware.oauth import oauth_middleware
from src.models.mcp import ToolExecutionContext
from src.models.errors import MCPError, ErrorCode


# Integration Test Video URL - known to have transcripts
INTEGRATION_TEST_VIDEO_URL = "https://www.youtube.com/watch?v=ILUsEN_Slf0"

# Mock the oauth_middleware to allow requests to pass through
@pytest.fixture(scope="module", autouse=True)
def mock_oauth_middleware():
    """Mocks the OAuth middleware to allow all requests to pass through."""
    async def mock_middleware(request, call_next):
        # Optionally, you can set a dummy auth_context if needed by the tool
        request.state.auth_context = MagicMock()
        return await call_next(request)

    # Patch the oauth_middleware function
    with patch("src.middleware.oauth.oauth_middleware", side_effect=mock_middleware):
        yield


@pytest.fixture(scope="module")
def client():
    # The lifespan events (including tool registration) are handled by TestClient
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_integration_youtube_transcript_retrieval(client):
    """
    Integration test: full workflow from API call to actual transcript retrieval.
    Tests with a known YouTube video (INTEGRATION_TEST_VIDEO_URL) that has transcripts.
    """
    # Verify the tool is registered via the /health endpoint first
    health_response = client.get("/health")
    assert health_response.status_code == status.HTTP_200_OK
    assert "get_youtube_transcript" in health_response.json().get("registered_tools", [])

    # Prepare the payload for tool invocation
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": INTEGRATION_TEST_VIDEO_URL},
    }

    # Invoke the tool
    response = client.post("/tools/invoke", json=payload)

    # Assert success status code
    assert response.status_code == status.HTTP_200_OK

    # Assert response structure and content
    response_json = response.json()
    assert "result" in response_json
    result = response_json["result"]

    assert result["video_id"] == "ILUsEN_Slf0"
    assert "full_text" in result
    assert "segments" in result
    assert len(result["segments"]) > 0

    # Assert a known phrase from the transcript (for robust checking)
    # This specific phrase is from the video's transcript.
    assert "There are thousands of systems and devices" in result["full_text"]


@pytest.mark.asyncio
async def test_integration_invalid_youtube_url(client):
    """
    Integration test: ensure invalid YouTube URLs are handled correctly.
    """
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": "https://not.a.youtube.url/video"},
    }

    response = client.post("/tools/invoke", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error_code"] == ErrorCode.INVALID_URL.value
    assert "Invalid YouTube URL provided" in response_json["error"]


@pytest.mark.asyncio
async def test_integration_video_without_transcript(client):
    """
    Integration test: ensure videos without transcripts are handled correctly.
    This video is known to have no transcript (as of last check).
    """
    VIDEO_NO_TRANSCRIPT_URL = "https://www.youtube.com/watch?v=Fj-0q56P7G8" # Example video known to have no transcript
    payload = {
        "tool_name": "get_youtube_transcript",
        "parameters": {"url": VIDEO_NO_TRANSCRIPT_URL},
    }

    response = client.post("/tools/invoke", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    response_json = response.json()
    assert response_json["error_code"] == ErrorCode.TRANSCRIPT_NOT_AVAILABLE.value
    assert "No transcript available for this video" in response_json["detail"]

