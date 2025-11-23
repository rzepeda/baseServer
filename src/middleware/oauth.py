"""OAuth2 middleware for verifying access tokens."""

async def oauth_middleware(request, call_next):
    """Placeholder for OAuth2 middleware when disabled."""
    # This middleware is intentionally non-functional for Story 1.3
    # It will be fully implemented in a later story (e.g., Story 2.1)
    return await call_next(request)