"""OAuth2 middleware for verifying access tokens."""

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response


async def oauth_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Placeholder for OAuth2 middleware when disabled."""
    # This middleware is intentionally non-functional for Story 1.3
    # It will be fully implemented in a later story (e.g., Story 2.1)
    return await call_next(request)
