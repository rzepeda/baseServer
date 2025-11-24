"""YouTube-specific data models."""

from pydantic import BaseModel, Field, field_validator


class YouTubeURL(BaseModel):
    """YouTube URL validation model."""

    url: str = Field(..., description="YouTube video URL")
    video_id: str | None = Field(None, description="Extracted video ID")

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate that the URL is a valid YouTube URL."""
        if not any(domain in v.lower() for domain in ["youtube.com", "youtu.be", "m.youtube.com"]):
            raise ValueError("Invalid YouTube URL")
        return v


class YouTubeTranscriptSegment(BaseModel):
    """Individual transcript segment."""

    text: str = Field(..., description="Transcript text")
    start: float = Field(..., description="Start time in seconds")
    duration: float = Field(..., description="Duration in seconds")


class YouTubeTranscript(BaseModel):
    """Complete YouTube transcript."""

    video_id: str = Field(..., description="YouTube video ID")
    segments: list[YouTubeTranscriptSegment] = Field(..., description="Transcript segments")
    full_text: str = Field(..., description="Full transcript as single string")
    language: str = Field(default="en", description="Transcript language code")
