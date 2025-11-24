# YouTube Transcript Extraction Tool - cURL Commands

This document provides `cURL` commands to test the YouTube Transcript Extraction Tool via the `/tools/invoke` endpoint of the MCP server.

**Assumption:** The MCP server is running locally on `http://localhost:8080`.

## 1. Successful Transcript Retrieval

This command fetches the transcript for a known YouTube video (Rick Astley - Never Gonna Give You Up).

**Endpoint:** `POST http://localhost:8080/tools/invoke`
**Tool Name:** `get_youtube_transcript`
**Parameters:** `url`

```bash
curl -X POST "http://localhost:8080/tools/invoke" \
     -H "Content-Type: application/json" \
     -d '{
           "tool_name": "get_youtube_transcript",
           "parameters": {
             "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
           }
         }'
```
```bash
curl -X POST "http://calendar-computational-bring-ever.trycloudflare.com:8080/tools/invoke" \
     -H "Content-Type: application/json" \
     -d '{
           "tool_name": "get_youtube_transcript",
           "parameters": {
             "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
           }
         }'
```      

```bash       
curl -X GET "https://calendar-computational-bring-ever.trycloudflare.com/tools/list"
```

**Expected Response (Status 200 OK):**
A JSON object containing the `video_id`, `full_text` of the transcript, and a list of `segments`. The `full_text` should contain phrases like "never gonna give you up".

## 2. Invalid YouTube URL

This command tests the error handling for an invalid or non-YouTube URL.

**Endpoint:** `POST http://localhost:8080/tools/invoke`
**Tool Name:** `get_youtube_transcript`
**Parameters:** `url`

```bash
curl -X POST "http://localhost:8080/tools/invoke" \
     -H "Content-Type: application/json" \
     -d '{
           "tool_name": "get_youtube_transcript",
           "parameters": {
             "url": "https://not.a.youtube.url/video"
           }
         }'
```

**Expected Response (Status 400 Bad Request):**
A JSON object with an `error_code` of `INVALID_URL` and a message indicating an invalid URL.

```json
{
  "error": "Invalid YouTube URL provided: Invalid YouTube URL",
  "error_code": "INVALID_URL"
}
```

## 3. Video Without Transcript (Transcripts Disabled)

This command tests the error handling for a YouTube video where transcripts are disabled.

**Endpoint:** `POST http://localhost:8080/tools/invoke`
**Tool Name:** `get_youtube_transcript`
**Parameters:** `url`

```bash
curl -X POST "http://localhost:8080/tools/invoke" \
     -H "Content-Type: application/json" \
     -d '{
           "tool_name": "get_youtube_transcript",
           "parameters": {
             "url": "https://www.youtube.com/watch?v=X2KSs7KwlGw"
           }
         }'
```

**Expected Response (Status 404 Not Found):**
A JSON object with an `error_code` of `TRANSCRIPT_NOT_AVAILABLE` and a message indicating transcripts are disabled.

```json
{
  "error": "Transcripts are disabled for this video.",
  "error_code": "TRANSCRIPT_NOT_AVAILABLE"
}
```

---
