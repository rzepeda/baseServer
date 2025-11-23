import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from src.tools.youtube_tool import YouTubeTool
from src.models.mcp import ToolExecutionContext
from src.models.errors import MCPError, ErrorCode
from youtube_transcript_api._errors import VideoUnavailable, NoTranscriptFound, InvalidVideoId
import requests


@dataclass
class MockSnippet:
    """Mock FetchedTranscriptSnippet for testing."""
    text: str
    start: float
    duration: float


@dataclass
class MockFetchedTranscript:
    """Mock FetchedTranscript for testing."""
    video_id: str
    language_code: str
    snippets: list


@pytest.fixture
def youtube_tool():
    return YouTubeTool()


@pytest.fixture
def mock_context():
    """Provides a mock ToolExecutionContext."""
    context = MagicMock(spec=ToolExecutionContext)
    context.logger = MagicMock()
    return context

@pytest.mark.asyncio
async def test_handler_success(youtube_tool, mock_context):
    """Test successful transcript retrieval."""
    url = "https://www.youtube.com/watch?v=ILUsEN_Slf0"
    params = {"url": url}

    mock_snippets = [
        MockSnippet(text="Hello world", start=0.5, duration=2.0),
        MockSnippet(text="This is a test", start=3.0, duration=2.5),
    ]
    mock_transcript = MockFetchedTranscript(
        video_id="ILUsEN_Slf0",
        language_code="en",
        snippets=mock_snippets
    )

    mock_api_instance = MagicMock()
    mock_api_instance.fetch.return_value = mock_transcript

    with patch("src.tools.youtube_tool.YouTubeTranscriptApi", return_value=mock_api_instance):
        result = await youtube_tool.handler(params, mock_context)

        mock_api_instance.fetch.assert_called_once_with("ILUsEN_Slf0")
        assert result.video_id == "ILUsEN_Slf0"
        assert result.full_text == "Hello world This is a test"
        assert len(result.segments) == 2
        assert result.segments[0].text == "Hello world"
        mock_context.logger.info.assert_any_call("youtube_tool.transcript_retrieved", video_id="ILUsEN_Slf0")


@pytest.mark.asyncio
@pytest.mark.parametrize("url, video_id", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
])
async def test_valid_url_formats(youtube_tool, mock_context, url, video_id):
    """Test various valid YouTube URL formats."""
    params = {"url": url}

    mock_transcript = MockFetchedTranscript(
        video_id=video_id,
        language_code="en",
        snippets=[]
    )
    mock_api_instance = MagicMock()
    mock_api_instance.fetch.return_value = mock_transcript

    with patch("src.tools.youtube_tool.YouTubeTranscriptApi", return_value=mock_api_instance):
        result = await youtube_tool.handler(params, mock_context)
        assert result.video_id == video_id

@pytest.mark.asyncio
@pytest.mark.parametrize("url, error_message", [
    ("https://www.google.com", "Invalid YouTube URL provided"),
    ("https://www.youtube.com/invalid_path", "Could not extract video ID"),
])
async def test_invalid_url_formats(youtube_tool, mock_context, url, error_message):
    """Test various invalid YouTube URL formats."""
    params = {"url": url}
    with pytest.raises(MCPError) as excinfo:
        await youtube_tool.handler(params, mock_context)
    
    assert excinfo.value.code == ErrorCode.INVALID_URL
    assert error_message in excinfo.value.message


@pytest.mark.asyncio
async def test_handler_no_url(youtube_tool, mock_context):
    """Test handler when no URL is provided."""
    params = {}
    with pytest.raises(MCPError) as excinfo:
        await youtube_tool.handler(params, mock_context)
    
    assert excinfo.value.code == ErrorCode.INVALID_URL
    assert "URL parameter is required" in excinfo.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize("api_exception, expected_error_code, expected_error_message", [
    (InvalidVideoId("some_video"), ErrorCode.INVALID_URL, "Invalid YouTube video ID"),
    (VideoUnavailable("some_video"), ErrorCode.YOUTUBE_API_ERROR, "YouTube video not found or unavailable"),
    (NoTranscriptFound("some_video", requested_language_codes=[], transcript_data=[]), ErrorCode.TRANSCRIPT_NOT_AVAILABLE, "No transcript available for this video"),
    (requests.exceptions.RequestException("Network issue"), ErrorCode.YOUTUBE_API_ERROR, "Network error while contacting YouTube"),
])
async def test_handler_api_errors(youtube_tool, mock_context, api_exception, expected_error_code, expected_error_message):
    """Test various errors from the YouTube Transcript API."""
    url = "https://www.youtube.com/watch?v=some_video"
    params = {"url": url}

    mock_api_instance = MagicMock()
    mock_api_instance.fetch.side_effect = api_exception

    with patch("src.tools.youtube_tool.YouTubeTranscriptApi", return_value=mock_api_instance):
        with pytest.raises(MCPError) as excinfo:
            await youtube_tool.handler(params, mock_context)

        assert excinfo.value.code == expected_error_code
        assert expected_error_message in excinfo.value.message


@pytest.mark.asyncio
async def test_handler_unexpected_error(youtube_tool, mock_context):
    """Test unexpected errors during handler execution."""
    url = "https://www.youtube.com/watch?v=some_video"
    params = {"url": url}

    mock_api_instance = MagicMock()
    mock_api_instance.fetch.side_effect = Exception("Unexpected error")

    with patch("src.tools.youtube_tool.YouTubeTranscriptApi", return_value=mock_api_instance):
        with pytest.raises(MCPError) as excinfo:
            await youtube_tool.handler(params, mock_context)

        assert excinfo.value.code == ErrorCode.TOOL_EXECUTION_ERROR
        assert "An unexpected error occurred" in excinfo.value.message
