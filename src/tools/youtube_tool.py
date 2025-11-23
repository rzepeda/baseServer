"""Tool for fetching YouTube video transcripts."""

from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from pydantic import ValidationError
from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
from youtube_transcript_api._errors import InvalidVideoId, NoTranscriptFound, VideoUnavailable  # type: ignore

from src.models.errors import ErrorCode, MCPError
from src.models.mcp import ToolExecutionContext
from src.models.youtube import YouTubeTranscript, YouTubeTranscriptSegment, YouTubeURL
from src.tools.base import BaseMCPTool


class YouTubeTool(BaseMCPTool):
    """A tool to fetch the transcript of a YouTube video."""

    @property
    def name(self) -> str:
        return "get_youtube_transcript"

    @property
    def description(self) -> str:
        return "Fetches the transcript for a given YouTube video URL. Supports standard (youtube.com), short (youtu.be), and mobile (m.youtube.com) URLs."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full YouTube video URL.",
                }
            },
            "required": ["url"],
        }

    def _extract_video_id(self, url: str) -> str | None:
        """Extracts the video ID from a YouTube URL."""
        parsed_url = urlparse(url)
        if parsed_url.hostname is not None and "youtube.com" in parsed_url.hostname:
            if parsed_url.path == "/watch":
                return parse_qs(parsed_url.query).get("v", [None])[0]
        elif parsed_url.hostname is not None and "youtu.be" in parsed_url.hostname:
            return parsed_url.path[1:]
        elif parsed_url.hostname is not None and "m.youtube.com" in parsed_url.hostname:
            if parsed_url.path == "/watch":
                return parse_qs(parsed_url.query).get("v", [None])[0]
        return None

    async def handler(self, params: dict[str, Any], context: ToolExecutionContext) -> YouTubeTranscript:
        url = params.get("url")
        if not url:
            raise MCPError(ErrorCode.INVALID_URL, "URL parameter is required.")

        try:
            youtube_url = YouTubeURL(url=url, video_id=None)
            video_id = self._extract_video_id(youtube_url.url)
            if not video_id:
                raise ValueError("Could not extract video ID from URL.")
            youtube_url.video_id = video_id

            context.logger.info("youtube_tool.video_id_extracted", video_id=video_id)

            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

            segments = [YouTubeTranscriptSegment(**item) for item in transcript_list]
            full_text = " ".join([segment.text for segment in segments])

            transcript = YouTubeTranscript(
                video_id=video_id,
                segments=segments,
                full_text=full_text,
                language="en" # Assuming english for now, can be enhanced later
            )

            context.logger.info("youtube_tool.transcript_retrieved", video_id=video_id)
            return transcript

        except (ValidationError, ValueError) as e:
            context.logger.warn("youtube_tool.invalid_url", url=url, error=str(e))
            raise MCPError(ErrorCode.INVALID_URL, f"Invalid YouTube URL provided: {e}") from e
        except InvalidVideoId as e:
            context.logger.warn("youtube_tool.invalid_video_id", video_id=video_id, error=str(e))
            raise MCPError(ErrorCode.INVALID_URL, f"Invalid YouTube video ID: {video_id}") from e
        except VideoUnavailable as e:
            context.logger.warn("youtube_tool.video_unavailable", video_id=video_id, error=str(e))
            raise MCPError(ErrorCode.YOUTUBE_API_ERROR, "YouTube video not found or unavailable.") from e
        except NoTranscriptFound as e:
            context.logger.info("youtube_tool.no_transcript_found", video_id=video_id, error=str(e))
            raise MCPError(ErrorCode.TRANSCRIPT_NOT_AVAILABLE, "No transcript available for this video.") from e
        except TranscriptsDisabled as e: # Explicitly handle TranscriptsDisabled
            context.logger.info("youtube_tool.transcripts_disabled", video_id=video_id, error=str(e))
            raise MCPError(ErrorCode.TRANSCRIPT_NOT_AVAILABLE, "Transcripts are disabled for this video.") from e
        except requests.exceptions.RequestException as e:
            context.logger.error("youtube_tool.network_error", video_id=video_id, error=str(e))
            raise MCPError(ErrorCode.YOUTUBE_API_ERROR, "Network error while contacting YouTube.") from e
        except Exception as e:
            context.logger.error("youtube_tool.unknown_error", video_id=video_id if 'video_id' in locals() else "unknown", error=str(e))
            raise MCPError(ErrorCode.TOOL_EXECUTION_ERROR, "An unexpected error occurred while fetching the transcript.") from e
