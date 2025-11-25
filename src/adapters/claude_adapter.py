"""Claude.ai compatible MCP adapter - pure JSON-RPC without SSE wrapping."""

import json

from starlette.requests import Request
from starlette.responses import Response

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeAIMCPAdapter:
    """
    ASGI middleware that converts FastMCP's SSE-wrapped responses to pure JSON.

    FastMCP returns responses in SSE format even in stateless mode:
        event: message
        data: {"jsonrpc":"2.0",...}

    Claude.ai expects pure JSON-RPC:
        {"jsonrpc":"2.0",...}

    This adapter unwraps the SSE format and returns pure JSON for /mcp endpoint.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        """ASGI interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Only process /mcp endpoint
        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        # Capture the response
        response_started = False
        status_code = 200
        response_headers = []
        body_parts = []

        async def send_wrapper(message):
            nonlocal response_started, status_code, response_headers, body_parts

            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    body_parts.append(body)

                # Check if this is the final chunk
                more_body = message.get("more_body", False)
                if not more_body:
                    # Process complete response
                    full_body = b"".join(body_parts)
                    try:
                        text = full_body.decode("utf-8")

                        # Parse SSE format: "event: message\ndata: {...}"
                        if "data: " in text:
                            lines = text.split("\n")
                            for line in lines:
                                if line.startswith("data: "):
                                    json_str = line[6:]  # Remove "data: " prefix
                                    # Validate it's valid JSON
                                    json.loads(json_str)

                                    logger.debug(
                                        "Unwrapped SSE to pure JSON", path=path
                                    )

                                    # Send pure JSON response
                                    json_bytes = json_str.encode("utf-8")
                                    await send({
                                        "type": "http.response.start",
                                        "status": status_code,
                                        "headers": [
                                            [b"content-type", b"application/json"],
                                            [b"content-length", str(len(json_bytes)).encode()],
                                        ],
                                    })
                                    await send({
                                        "type": "http.response.body",
                                        "body": json_bytes,
                                        "more_body": False,
                                    })
                                    return
                    except Exception as e:
                        logger.error(
                            "Failed to unwrap SSE response",
                            error=str(e),
                            exc_info=True,
                        )

                    # If unwrapping failed, send original response
                    await send({
                        "type": "http.response.start",
                        "status": status_code,
                        "headers": response_headers,
                    })
                    await send({
                        "type": "http.response.body",
                        "body": full_body,
                        "more_body": False,
                    })

        await self.app(scope, receive, send_wrapper)
